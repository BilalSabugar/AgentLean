import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path

from agentlean import __version__
from agentlean.cli import main
from agentlean.install import install
from agentlean.storage import file_lock
from agentlean.trials import Trial, load_trials, record_trial, summarize


def trial(**overrides):
    values = dict(
        task="fix-parser",
        agent="codex",
        model="chosen-model",
        effort="medium",
        variant="baseline",
        pair="repeat-1",
        revision="abc123",
        environment="python-3.11-linux",
        criteria="parser-v1",
        result="pass",
        minutes=10,
        evidence=["test_parser: PASS"],
    )
    values.update(overrides)
    return Trial(**values)


class TrialTests(unittest.TestCase):
    def test_invalid_measurements(self):
        for values in (
            {"minutes": -1},
            {"minutes": float("nan")},
            {"minutes": float("inf")},
            {"minutes": True},
            {"result": "great"},
            {"evidence": []},
            {"evidence": "passed"},
            {"iterations": -1},
            {"corrections": 1.5},
            {"task": " "},
            {"allowance_before_pct": 50},
            {"allowance_before_pct": 50, "allowance_after_pct": 60, "allowance_scope": "weekly"},
            {"allowance_before_pct": 101, "allowance_after_pct": 20, "allowance_scope": "weekly"},
            {"allowance_before_pct": 50, "allowance_after_pct": 40},
            {"observed_at": "2026-11-01T12:00:00"},
            {"schema_version": 2},
        ):
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                trial(**values)

    def test_roundtrip_duplicate_and_corrupt_log_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "runs.jsonl"
            original = trial(notes="Unicode: μ\nmultiline")
            record_trial(path, original)
            self.assertEqual(load_trials(path), [original])
            contents = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "duplicate"):
                record_trial(path, trial())
            self.assertEqual(path.read_bytes(), contents)
            path.write_text(path.read_text() + "{broken", encoding="utf-8")
            contents = path.read_bytes()
            with self.assertRaisesRegex(ValueError, ":2:"):
                record_trial(path, trial(pair="repeat-2"))
            self.assertEqual(path.read_bytes(), contents)
            self.assertTrue(path.with_suffix(".jsonl.lock").exists())

    def test_concurrent_writer_lock_does_not_modify_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            lock = Path(str(path) + ".lock")
            with file_lock(lock):
                with self.assertRaisesRegex(ValueError, "locked"):
                    with file_lock(lock, timeout=0.05):
                        self.fail("second lock unexpectedly acquired")
            self.assertFalse(path.exists())
            self.assertTrue(lock.exists())

    def test_pairs_include_failures_and_exclude_unmatched_runs_from_ratios(self):
        runs = [
            trial(),
            trial(variant="lean", minutes=5),
            trial(pair="repeat-2"),
            trial(pair="repeat-2", variant="lean", result="fail", minutes=1),
            trial(pair="repeat-3", variant="lean", minutes=100),
        ]
        group = summarize(runs)["groups"][0]
        self.assertEqual(group["matched_pairs"], 2)
        self.assertEqual(group["unmatched_runs"], 1)
        self.assertEqual(group["paired_outcomes"], {"pass->pass": 1, "pass->fail": 1})
        self.assertEqual(
            group["time_reduction"], {"n": 1, "median_pct": 50, "min_pct": 50, "max_pct": 50}
        )
        self.assertEqual(group["variants"]["lean"]["failed"], 1)
        self.assertEqual(group["variants"]["lean"]["total_minutes"], 106)

    def test_only_identical_conditions_pair(self):
        for change in (
            {"agent": "claude"},
            {"model": "another"},
            {"effort": "high"},
            {"revision": "different"},
            {"environment": "windows"},
            {"criteria": "v2"},
            {"task": "other"},
            {"pair": "other"},
        ):
            with self.subTest(change=change):
                groups = summarize([trial(), trial(variant="lean", **change)])["groups"]
                self.assertEqual(sum(g["matched_pairs"] for g in groups), 0)

    def test_usage_scopes_and_rounding(self):
        usage = dict(
            allowance_before_pct=80, allowance_after_pct=70, allowance_scope="codex/plan/weekly"
        )
        baseline = trial(**usage)
        lean = trial(variant="lean", **{**usage, "allowance_after_pct": 75})
        group = summarize([baseline, lean])["groups"][0]
        self.assertEqual(group["allowance_reduction"]["median_pct"], 50)
        rounded = replace(lean, allowance_after_pct=80)
        self.assertEqual(summarize([baseline, rounded])["groups"][0]["allowance_reduction"]["n"], 0)
        different_scope = replace(lean, allowance_scope="codex/other-plan/weekly")
        self.assertEqual(
            sum(g["matched_pairs"] for g in summarize([baseline, different_scope])["groups"]), 0
        )

    def test_regression_stays_negative_and_empty_report_has_no_savings(self):
        group = summarize([trial(), trial(variant="lean", minutes=15)])["groups"][0]
        self.assertEqual(group["time_reduction"]["median_pct"], -50)
        self.assertEqual(summarize([])["groups"], [])

    def test_completion_efficiency_accounts_for_failed_run_consumption(self):
        usage = dict(
            allowance_before_pct=80, allowance_after_pct=70, allowance_scope="product/plan/weekly"
        )
        runs = [trial(**usage), trial(pair="2", result="fail", **usage)]
        baseline = summarize(runs)["groups"][0]["variants"]["baseline"]
        self.assertEqual(baseline["observed_allowance_runs"], 2)
        self.assertEqual(baseline["allowance_consumed_pct_points"], 20)
        self.assertEqual(baseline["verified_completions_per_pct_point"], 0.05)

    def test_duplicate_ids_rejected_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            record_trial(path, trial())
            path.write_bytes(path.read_bytes() * 2)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_trials(path)


class InstallationTests(unittest.TestCase):
    def test_preview_writes_nothing_and_apply_preserves_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("user-owned instructions", encoding="utf-8")
            install(root, "codex")
            self.assertEqual(list(root.iterdir()), [root / "AGENTS.md"])
            install(root, "codex", apply=True)
            skill = root / ".agents/skills/agentlean/SKILL.md"
            self.assertTrue(skill.is_file())
            self.assertEqual((root / "AGENTS.md").read_text(), "user-owned instructions")
            original = skill.read_bytes()
            self.assertIn("UNCHANGED", " ".join(install(root, "codex", apply=True)))
            self.assertEqual(skill.read_bytes(), original)

    def test_profiles_create_expected_paths_without_global_settings(self):
        for agent, path in (
            ("codex", ".agents/skills/agentlean/SKILL.md"),
            ("claude", ".claude/skills/agentlean/SKILL.md"),
            ("generic", ".agentlean/workflow.md"),
        ):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                install(root, agent, apply=True)
                self.assertTrue((root / path).is_file())
                instructions = "CLAUDE.md" if agent == "claude" else "AGENTS.md"
                self.assertTrue((root / instructions).is_file())
                self.assertTrue((root / f".agentlean/install-{agent}.json").is_file())

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            try:
                (root / ".agents").symlink_to(outside, target_is_directory=True)
            except OSError:
                if os.name != "nt":
                    self.skipTest("creating symlinks requires OS permission")
                link = str(root / ".agents").replace("'", "''")
                destination = outside.replace("'", "''")
                result = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        f"New-Item -ItemType Junction -Path '{link}' -Value '{destination}' -ErrorAction Stop | Out-Null",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=15,
                )
                if result.returncode:
                    self.skipTest("OS does not permit symlink or junction creation")
            try:
                with self.assertRaisesRegex(ValueError, "escapes"):
                    install(root, "codex", apply=True)
                self.assertEqual(list(Path(outside).iterdir()), [])
                self.assertFalse((root / "AGENTS.md").exists())
            finally:
                link = root / ".agents"
                if link.is_symlink():
                    link.unlink()
                elif os.name == "nt":
                    link.rmdir()  # Removes the junction, not its target.


class CLITests(unittest.TestCase):
    def invoke(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_record_report_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "runs.jsonl")
            arguments = [
                "trial",
                "--file",
                path,
                "--task",
                "T1",
                "--agent",
                "codex",
                "--model",
                "M",
                "--effort",
                "medium",
                "--pair",
                "1",
                "--revision",
                "abc",
                "--environment",
                "dev-v1",
                "--criteria",
                "unit-v1",
                "--variant",
                "baseline",
                "--result",
                "pass",
                "--minutes",
                "4",
                "--evidence",
                "unit tests passed",
            ]
            self.assertEqual(self.invoke(arguments)[0], 0)
            code, output, _ = self.invoke(["report", "--file", path])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output)["groups"][0]["unmatched_runs"], 1)
            self.assertEqual(self.invoke(arguments)[0], 2)
            self.assertEqual(self.invoke(["report", "--file", path + ".missing"])[0], 2)

    def test_module_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "-m", "agentlean", "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), __version__)


if __name__ == "__main__":
    unittest.main()
