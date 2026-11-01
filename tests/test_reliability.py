"""Fault injection, process contention, recovery and input-boundary regression tests."""

import base64
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import test_agentlean as support

from agentlean.install import install, recover
from agentlean.storage import atomic_write, strict_json
from agentlean.trials import load_trials, record_trial

trial = support.trial


class ReliabilityTests(unittest.TestCase):
    def test_temporary_windows_sharing_violation_retries_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value"
            path.write_bytes(b"before")
            import os

            replace = os.replace
            sharing = PermissionError("temporary sharing violation")
            sharing.winerror = 32
            attempts = []

            def retry(source, destination):
                attempts.append(destination)
                if len(attempts) == 1:
                    raise sharing
                replace(source, destination)

            with patch("agentlean.storage.os.replace", side_effect=retry):
                atomic_write(path, b"after")
            self.assertEqual(path.read_bytes(), b"after")
            self.assertEqual(len(attempts), 2)

    def test_replace_failure_preserves_log_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            record_trial(path, trial())
            original = path.read_bytes()
            with patch("agentlean.storage.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    record_trial(path, trial(pair="second"))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])
            record_trial(path, trial(pair="second"))
            self.assertEqual(len(load_trials(path)), 2)

    def test_process_writers_preserve_every_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            code = (
                "import json,sys; from agentlean.trials import Trial,record_trial; "
                "from pathlib import Path; record_trial(Path(sys.argv[1]),Trial(**json.loads(sys.argv[2])))"
            )
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", code, str(path), json.dumps(asdict(trial(pair=str(i))))],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for i in range(8)
            ]
            try:
                for process in processes:
                    _, error = process.communicate(timeout=20)
                    self.assertEqual(process.returncode, 0, error)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()
            self.assertEqual({t.pair for t in load_trials(path)}, {str(i) for i in range(8)})

    def test_killed_process_releases_os_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            code = (
                "from agentlean.storage import file_lock; from pathlib import Path; import sys; "
                "\nwith file_lock(Path(sys.argv[1])):\n print('locked',flush=True)\n sys.stdin.read()"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", code, str(path) + ".lock"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "locked")
            finally:
                process.kill()
                process.communicate(timeout=10)
            record_trial(path, trial())
            self.assertEqual(len(load_trials(path)), 1)

    def test_recovery_after_real_process_exit_during_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instructions = root / "AGENTS.md"
            instructions.write_bytes(b"user instructions")
            code = (
                "import os,sys; from pathlib import Path; import agentlean.install as installer\n"
                "write = installer.atomic_write\n"
                "def interrupted(path, content):\n"
                " write(path, content)\n"
                " if path.name == 'SKILL.md': os._exit(99)\n"
                "installer.atomic_write = interrupted\n"
                "installer.install(Path(sys.argv[1]), 'codex', apply=True)\n"
            )
            completed = subprocess.run(
                [sys.executable, "-c", code, str(root)],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            self.assertEqual(completed.returncode, 99, completed.stderr)
            skill = root / ".agents/skills/agentlean/SKILL.md"
            self.assertTrue(skill.is_file())
            recover(root, apply=True)
            self.assertFalse(skill.exists())
            self.assertEqual(instructions.read_bytes(), b"user instructions")
            install(root, "codex", apply=True)
            self.assertTrue(skill.is_file())

    def test_installer_rolls_back_failed_manifest_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(path, content):
                if path.name == "install-codex.json":
                    raise OSError("simulated full disk")
                atomic_write(path, content)

            with patch("agentlean.install.atomic_write", side_effect=write):
                with self.assertRaisesRegex(OSError, "full disk"):
                    install(root, "codex", apply=True)
            self.assertFalse((root / ".agents/skills/agentlean/SKILL.md").exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".agentlean/install-transaction.json").exists())
            install(root, "codex", apply=True)

    def test_upgrade_and_uninstall_preserve_user_edits_and_trial_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install(root, "generic", apply=True)
            record_trial(root / ".agentlean/trials.jsonl", trial())
            workflow = root / ".agentlean/workflow.md"
            original = workflow.read_bytes()
            workflow.write_bytes(original + b"user edits")
            for kwargs in ({"upgrade": True}, {"remove": True}):
                with self.assertRaisesRegex(ValueError, "modified"):
                    install(root, "generic", apply=True, **kwargs)
                self.assertTrue(workflow.read_bytes().endswith(b"user edits"))
            workflow.write_bytes(original)
            install(root, "generic", remove=True)
            self.assertTrue(workflow.is_file())
            install(root, "generic", apply=True, remove=True)
            self.assertFalse(workflow.exists())
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertEqual(len(load_trials(root / ".agentlean/trials.jsonl")), 1)

    def test_upgrade_requires_opt_in_and_verifies_owned_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install(root, "codex", apply=True)
            workflow = root / ".agents/skills/agentlean/SKILL.md"
            workflow.write_bytes(b"old release")
            manifest = root / ".agentlean/install-codex.json"
            data = json.loads(manifest.read_text())
            data["version"] = "0.1.0"
            data["files"][".agents/skills/agentlean/SKILL.md"] = sha256(b"old release").hexdigest()
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "upgrade"):
                install(root, "codex", apply=True)
            install(root, "codex", upgrade=True)
            self.assertEqual(workflow.read_bytes(), b"old release")
            install(root, "codex", apply=True, upgrade=True)
            self.assertNotEqual(workflow.read_bytes(), b"old release")

    def test_recovery_detects_interruption_and_preserves_later_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = root / ".agentlean"
            metadata.mkdir()
            journal = metadata / "install-transaction.json"
            journal.write_text(
                json.dumps(
                    {
                        "AGENTS.md": {
                            "before": None,
                            "after": base64.b64encode(b"generated").decode(),
                        }
                    }
                )
            )
            instructions = root / "AGENTS.md"
            instructions.write_bytes(b"generated")
            with self.assertRaisesRegex(ValueError, "interrupted"):
                install(root, "codex")
            recover(root)
            self.assertTrue(instructions.exists())
            instructions.write_bytes(b"later user edit")
            with self.assertRaisesRegex(ValueError, "changed since"):
                recover(root, apply=True)
            instructions.write_bytes(b"generated")
            recover(root, apply=True)
            self.assertFalse(instructions.exists())
            self.assertFalse(journal.exists())

    def test_manifest_cannot_remove_arbitrary_user_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install(root, "generic", apply=True)
            private = root / "private.txt"
            private.write_bytes(b"user data")
            manifest = root / ".agentlean/install-generic.json"
            data = json.loads(manifest.read_text())
            data["files"]["private.txt"] = sha256(private.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "invalid"):
                install(root, "generic", apply=True, remove=True)
            self.assertEqual(private.read_bytes(), b"user data")

    def test_strict_json_and_persisted_identity(self):
        for text in ('{"key":1,"key":2}', '{"key":NaN}', '{"key":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                strict_json(text)
        for field in ("trial_id", "observed_at"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "runs.jsonl"
                data = asdict(trial())
                data[field] = ""
                path.write_text(json.dumps(data) + "\n")
                with self.assertRaisesRegex(ValueError, "identity"):
                    load_trials(path)


class ProductionCLITests(unittest.TestCase):
    invoke = support.CLITests.invoke

    def test_cli_install_remove_and_conflict_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.invoke(["init", directory, "--agent", "claude", "--apply"])[0], 0)
            self.assertTrue((Path(directory) / "CLAUDE.md").exists())
            self.assertEqual(self.invoke(["recover", directory])[0], 2)
            self.assertEqual(self.invoke(["uninstall", directory, "--agent", "claude"])[0], 0)
            self.assertTrue((Path(directory) / "CLAUDE.md").exists())
            self.assertEqual(
                self.invoke(["uninstall", directory, "--agent", "claude", "--apply"])[0], 0
            )
            self.assertFalse((Path(directory) / "CLAUDE.md").exists())

    def test_corrupt_input_returns_error_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text('{"broken":NaN}\n')
            code, output, error = self.invoke(["check", "--file", str(path)])
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn(":1:", error)
            self.assertNotIn("Traceback", error)

    def test_check_output_and_log_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.jsonl"
            record_trial(path, trial())
            original = path.read_bytes()
            self.assertEqual(self.invoke(["check", "--file", str(path)])[0], 0)
            self.assertEqual(
                self.invoke(["report", "--file", str(path), "--output", str(path)])[0], 2
            )
            self.assertEqual(path.read_bytes(), original)
            report = Path(directory) / "report.json"
            self.assertEqual(
                self.invoke(["report", "--file", str(path), "--output", str(report)])[0], 0
            )
            self.assertEqual(json.loads(report.read_text())["schema_version"], 1)
