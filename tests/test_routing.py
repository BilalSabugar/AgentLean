"""Model selection, feature toggles and native launcher contract tests."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_agentlean as support

from agentlean.routing import AGENTS, TIERS, configure, launch, plan, select_tier, settings


def presets(root, agent="codex"):
    for tier, effort in zip(TIERS, ("low", "medium", "high"), strict=True):
        configure(root, agent=agent, tier=tier, model=f"test-{agent}-{tier}", effort=effort)


class RoutingTests(unittest.TestCase):
    def test_concurrent_updates_preserve_both_provider_presets(self):
        with tempfile.TemporaryDirectory() as directory:
            code = (
                "import sys; from pathlib import Path; from agentlean.routing import configure; "
                "configure(Path(sys.argv[1]),agent=sys.argv[2],tier=sys.argv[3],model=sys.argv[2]+'-'+sys.argv[3])"
            )
            workers = [
                subprocess.Popen(
                    [sys.executable, "-c", code, directory, agent, tier],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for agent in AGENTS
                for tier in TIERS
            ]
            try:
                for worker in workers:
                    _, error = worker.communicate(timeout=15)
                    self.assertEqual(worker.returncode, 0, error)
            finally:
                for worker in workers:
                    if worker.poll() is None:
                        worker.kill()
                    worker.communicate()
            saved = settings(Path(directory))
            for agent in AGENTS:
                self.assertEqual(set(saved["agents"][agent]), set(TIERS))

    def test_windows_batch_wrapper_is_rejected_without_launch(self):
        if os.name != "nt":
            return  # Native executable handling is platform-specific.
        with tempfile.TemporaryDirectory() as directory:
            decision = plan(Path(directory), "codex", "Task")
            with (
                patch("agentlean.routing.shutil.which", return_value="client.cmd"),
                patch("agentlean.routing.subprocess.run") as runner,
            ):
                with self.assertRaisesRegex(ValueError, "native .exe"):
                    launch(decision, "Task")
                runner.assert_not_called()

    def test_default_off_status_and_preview_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(settings(root)["enabled"])
            for agent in AGENTS:
                decision = plan(root, agent, "Implement a new endpoint")
                self.assertFalse(decision["routing_enabled"])
                self.assertIsNone(decision["model"])
                self.assertEqual(decision["effort"], "native")
                self.assertNotIn("--model", decision["argv"])
            self.assertEqual(list(root.iterdir()), [])

    def test_toggle_roundtrip_preserves_presets_and_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            presets(root)
            presets(root, "claude")
            user = root / "AGENTS.md"
            user.write_text("user-owned")
            before = settings(root)["agents"]
            self.assertTrue(configure(root, enabled=True)["enabled"])
            self.assertFalse(configure(root, enabled=False)["enabled"])
            self.assertEqual(settings(root)["agents"], before)
            self.assertEqual(user.read_text(), "user-owned")

    def test_tier_selection_and_explicit_hints(self):
        examples = [
            ("Fix a typo in README", {}, "fast"),
            ("Implement pagination", {}, "balanced"),
            ("Fix a typo and implement a parser", {}, "balanced"),
            ("Refactor concurrent workers", {}, "deep"),
            ("Fix a typo in authentication docs", {}, "deep"),
            ("Fix a typo", {"risk": "high"}, "deep"),
            ("Small change", {"complexity": "simple"}, "fast"),
            ("Refactor a small helper", {"complexity": "standard"}, "balanced"),
            ("Small change", {"complexity": "complex"}, "deep"),
            ("Fix typo", {"failed_attempts": 1}, "balanced"),
            ("Fix typo", {"failed_attempts": 2}, "deep"),
            ("Implement pagination", {"failed_attempts": 1}, "deep"),
        ]
        for task, options, expected in examples:
            with self.subTest(task=task, options=options):
                self.assertEqual(select_tier(task, **options)[0], expected)
        for options in (
            {"task": " "},
            {"task": "test", "failed_attempts": -1},
            {"task": "test", "failed_attempts": True},
            {"task": "test", "complexity": "unknown"},
            {"task": "test", "risk": "unknown"},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                select_tier(**options)

    def test_codex_and_claude_receive_provider_specific_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for agent in AGENTS:
                presets(root, agent)
            configure(root, enabled=True)
            codex = plan(root, "codex", "Fix typo", has_checks=True)
            self.assertEqual(
                codex["argv"],
                [
                    "codex",
                    "exec",
                    "--model",
                    "test-codex-fast",
                    "-c",
                    'model_reasoning_effort="low"',
                    "-",
                ],
            )
            claude = plan(root, "claude", "Refactor worker pools")
            self.assertEqual(
                claude["argv"], ["claude", "-p", "--model", "test-claude-deep", "--effort", "high"]
            )
            self.assertNotIn("Fix typo", json.dumps(codex))
            self.assertNotIn(
                "Refactor worker pools", (root / ".agentlean/routing.json").read_text()
            )
            disabled = plan(root, "claude", "Refactor worker pools", routing="off")
            self.assertEqual(disabled["argv"], ["claude", "-p"])
            self.assertTrue(settings(root)["enabled"])

    def test_unconfigured_models_fail_and_native_effort_is_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configure(root, enabled=True)
            with self.assertRaisesRegex(ValueError, "no codex/balanced"):
                plan(root, "codex", "Implement pagination")
            configure(root, agent="codex", tier="balanced", model="account-model")
            result = plan(root, "codex", "Implement pagination")
            self.assertEqual(result["argv"], ["codex", "exec", "--model", "account-model", "-"])
            with self.assertRaisesRegex(ValueError, "no claude/balanced"):
                plan(root, "claude", "Implement pagination")

    def test_one_run_override_does_not_change_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            presets(root)
            self.assertTrue(plan(root, "codex", "Fix typo", routing="on")["routing_enabled"])
            self.assertFalse(settings(root)["enabled"])
            self.assertIsNone(plan(root, "codex", "Fix typo")["model"])

    def test_invalid_configuration_preserves_previous_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            presets(root)
            path = root / ".agentlean/routing.json"
            original = path.read_bytes()
            for options in (
                {"agent": "codex", "tier": "fast", "model": "--config=evil"},
                {"agent": "codex", "tier": "fast", "model": "test\nmodel"},
                {"agent": "codex", "tier": "fast", "model": " "},
                {"agent": "codex", "tier": "fast", "model": "test", "effort": "invalid"},
                {"agent": "claude", "tier": "fast", "model": "test", "effort": "ultra"},
                {"agent": "unknown", "tier": "fast", "model": "test"},
                {"enabled": "yes"},
            ):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    configure(root, **options)
                self.assertEqual(path.read_bytes(), original)
            path.write_text('{"schema_version":1,"enabled":true,"enabled":false,"agents":{}}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                settings(root)

    def test_malformed_schema_is_rejected(self):
        invalid = [
            [],
            {},
            {"schema_version": 1, "enabled": "yes", "agents": {}},
            {"schema_version": 1, "enabled": False, "agents": {"other": {}}},
            {"schema_version": 1, "enabled": False, "agents": {"codex": {"unknown": {}}}},
            {"schema_version": 1, "enabled": False, "agents": {"codex": {"fast": {}}}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".agentlean/routing.json"
            path.parent.mkdir()
            for value in invalid:
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    settings(root)

    def test_launcher_uses_stdin_preserves_permissions_and_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            decision = plan(Path(directory), "codex", "Task")
            with (
                patch("agentlean.routing.shutil.which", return_value="native-client.exe"),
                patch(
                    "agentlean.routing.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 7),
                ) as runner,
            ):
                self.assertEqual(launch(decision, 'Task with "quotes"; $(example)'), 7)
                args, kwargs = runner.call_args
                self.assertEqual(args[0], ["native-client.exe", "exec", "-"])
                self.assertFalse(kwargs["shell"])
                self.assertEqual(kwargs["cwd"], directory)
                self.assertEqual(kwargs["input"], 'Task with "quotes"; $(example)')
            with patch("agentlean.routing.shutil.which", return_value=None):
                with self.assertRaisesRegex(ValueError, "not on PATH"):
                    launch(decision, "Task")

    def test_real_subprocess_prompt_and_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "fake_client.py"
            child.write_text(
                "import json,sys; from pathlib import Path; "
                "Path('observed.json').write_text(json.dumps({'prompt':sys.stdin.buffer.read().decode('utf-8'),'cwd':str(Path.cwd())})); "
                "sys.exit(6)"
            )
            decision = plan(root, "claude", "Task")
            with (
                patch("agentlean.routing.shutil.which", return_value=sys.executable),
                patch("agentlean.routing.command", return_value=[sys.executable, str(child)]),
            ):
                self.assertEqual(launch(decision, "Unicode prompt: μ; `literal`"), 6)
            observed = json.loads((root / "observed.json").read_text())
            self.assertEqual(observed["prompt"], "Unicode prompt: μ; `literal`")
            self.assertEqual(Path(observed["cwd"]), root)


class RoutingCLITests(unittest.TestCase):
    invoke = support.CLITests.invoke

    def test_switch_and_set_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            common = ["routing", "--target", directory]
            self.assertFalse(json.loads(self.invoke([*common, "status"])[1])["enabled"])
            self.assertEqual(
                self.invoke(
                    [
                        *common,
                        "set",
                        "--agent",
                        "codex",
                        "--tier",
                        "fast",
                        "--model",
                        "account-model",
                        "--effort",
                        "low",
                    ]
                )[0],
                0,
            )
            self.assertTrue(json.loads(self.invoke([*common, "on"])[1])["enabled"])
            self.assertFalse(json.loads(self.invoke([*common, "off"])[1])["enabled"])

    def test_preview_never_launches_and_explicit_execution_forwards_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["run", "--target", directory, "--agent", "codex", "--task", "Fix typo"]
            with patch("agentlean.cli.launch", return_value=9) as runner:
                self.assertEqual(self.invoke(args)[0], 0)
                runner.assert_not_called()
                self.assertEqual(self.invoke([*args, "--execute"])[0], 9)
                self.assertEqual(runner.call_args.args[1], "Fix typo")

    def test_stdin_task_and_invalid_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ["run", "--target", directory, "--agent", "claude", "--task", "-"]
            with patch("sys.stdin", io.StringIO("Fix typo")):
                self.assertEqual(self.invoke(args)[0], 0)
            self.assertEqual(self.invoke([*args[:-1], "Task", "--failed-attempts", "-1"])[0], 2)
