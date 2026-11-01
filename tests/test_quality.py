"""Acceptance checks govern success, spending and escalation decisions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_agentlean as support
from test_routing import presets

from agentlean.quality import execute, load_gates, run_checks
from agentlean.routing import configure, plan, repair_plans


def gates_file(
    root, program="from pathlib import Path; assert Path('value').read_text() == 'good'"
):
    path = root / "checks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checks": [
                    {
                        "name": "acceptance",
                        "argv": ["{python}", "-c", program],
                        "timeout_seconds": 5,
                    }
                ],
            }
        )
    )
    return path


def prepare(root, program=None):
    presets(root)
    configure(root, enabled=True)
    (root / "value").write_text("good")
    path = gates_file(root) if program is None else gates_file(root, program)
    return plan(root, "codex", "Fix typo", has_checks=True), load_gates(path)


class QualityTests(unittest.TestCase):
    def test_fast_requires_gates_and_mixed_task_is_not_fast(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, _ = prepare(root)
            self.assertEqual(decision["tier"], "fast")
            self.assertEqual(plan(root, "codex", "Fix typo")["tier"], "balanced")
            self.assertEqual(
                plan(root, "codex", "Fix typo and optimize performance", has_checks=True)["tier"],
                "balanced",
            )
            self.assertEqual(
                plan(root, "codex", "Fix security bug", has_checks=True)["tier"], "deep"
            )

    def test_failed_baseline_spends_no_model_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            (root / "value").write_text("broken before run")
            with patch("agentlean.quality.launch") as client:
                code, report = execute(decision, "Fix typo", gates)
            client.assert_not_called()
            self.assertEqual(code, 4)
            self.assertEqual(report["status"], "baseline_failed")
            self.assertEqual(report["attempts"], [])
            self.assertEqual(
                json.loads(Path(report["report_path"]).read_text())["status"], "baseline_failed"
            )

    def test_success_runs_all_checks_and_stores_no_task_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            with patch("agentlean.quality.launch", return_value=0) as client:
                code, report = execute(decision, "private unique prompt", gates, maximum_repairs=2)
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "checks_passed")
            self.assertGreaterEqual(report["elapsed_seconds"], 0)
            self.assertGreaterEqual(report["attempts"][0]["client_seconds"], 0)
            self.assertEqual(client.call_count, 1)
            self.assertEqual(len(report["attempts"]), 1)
            self.assertNotIn("private unique prompt", Path(report["report_path"]).read_text())
            self.assertTrue(Path(report["attempts"][0]["validation"]["checks"][0]["log"]).is_file())

    def test_native_success_cannot_hide_bad_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)

            def bad_result(*_):
                (root / "value").write_text("bad")
                return 0

            with patch("agentlean.quality.launch", side_effect=bad_result) as client:
                code, report = execute(decision, "Task", gates)
            self.assertEqual(code, 4)
            self.assertEqual(report["status"], "checks_failed")
            self.assertEqual(client.call_count, 1)

    def test_later_regression_check_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            data = json.loads(gates.path.read_text())
            data["checks"].insert(
                0, {"name": "cheap first check", "argv": ["{python}", "-c", "pass"]}
            )
            gates.path.write_text(json.dumps(data))
            gates = load_gates(gates.path)

            def break_output(*_):
                (root / "value").write_text("regression")
                return 0

            with patch("agentlean.quality.launch", side_effect=break_output):
                code, report = execute(decision, "Task", gates)
            self.assertEqual(code, 4)
            result = report["attempts"][0]["validation"]
            self.assertEqual([check["status"] for check in result["checks"]], ["pass", "fail"])
            self.assertEqual(result["planned_checks"], 2)

    def test_escalation_happens_only_after_validation_and_keeps_completed_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            observed = []

            def work(candidate, prompt):
                observed.append((candidate, prompt))
                if len(observed) == 1:
                    (root / "completed").write_text("preserve this")
                    (root / "value").write_text("bad")
                else:
                    self.assertTrue((root / "completed").exists())
                    (root / "value").write_text("good")
                return 0

            with patch("agentlean.quality.launch", side_effect=work):
                code, report = execute(decision, "Task", gates, maximum_repairs=1)
            self.assertEqual(code, 0)
            self.assertEqual([item[0]["tier"] for item in observed], ["fast", "balanced"])
            self.assertIn("acceptance check failed", observed[1][1])
            self.assertLess(len(observed[1][1]), 5000)
            self.assertEqual(report["attempts"][0]["validation"]["status"], "fail")

    def test_repeated_failure_stops_before_spending_on_deep(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(
                root,
                "from pathlib import Path; import sys; print('fixed diagnostic'); sys.exit(0 if Path('value').read_text()=='good' else 1)",
            )

            def fail(*_):
                (root / "value").write_text("bad")
                return 0

            with patch("agentlean.quality.launch", side_effect=fail) as client:
                code, report = execute(decision, "Task", gates, maximum_repairs=2)
            self.assertEqual(code, 4)
            self.assertEqual(report["status"], "repeated_failure")
            self.assertEqual(client.call_count, 2)

    def test_client_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            decision, gates = prepare(Path(directory))
            with patch("agentlean.quality.launch", return_value=7) as client:
                code, report = execute(decision, "Task", gates, maximum_repairs=2)
            self.assertEqual(code, 7)
            self.assertEqual(client.call_count, 1)
            self.assertEqual(report["status"], "client_failed")
            self.assertIsNone(report["attempts"][0]["validation"])

    def test_cli_error_persists_evidence_before_propagating(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            with patch("agentlean.quality.launch", side_effect=ValueError("client absent")):
                with self.assertRaisesRegex(ValueError, "absent"):
                    execute(decision, "Task", gates)
            reports = list((root / ".agentlean/runs").glob("*/report.json"))
            self.assertEqual(json.loads(reports[0].read_text())["status"], "client_error")

    def test_known_red_baseline_requires_explicit_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)
            (root / "value").write_text("known bug")

            def fix(*_):
                (root / "value").write_text("good")
                return 0

            with patch("agentlean.quality.launch", side_effect=fix):
                code, report = execute(decision, "Fix bug", gates, allow_failing_baseline=True)
            self.assertEqual(code, 0)
            self.assertEqual(report["baseline"]["status"], "fail")

    def test_changed_gate_manifest_blocks_success_and_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, gates = prepare(root)

            def tamper(*_):
                gates.path.write_text("{}")
                return 0

            with patch("agentlean.quality.launch", side_effect=tamper) as client:
                code, report = execute(decision, "Task", gates, maximum_repairs=2)
            self.assertEqual(code, 4)
            self.assertEqual(report["status"], "validation_blocked")
            self.assertEqual(client.call_count, 1)

    def test_timeouts_errors_and_early_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = gates_file(root, "import time; time.sleep(1)")
            data = json.loads(path.read_text())
            data["checks"][0]["timeout_seconds"] = 0.05
            data["checks"].append(
                {"name": "later", "argv": ["{python}", "-c", "raise SystemExit(0)"]}
            )
            path.write_text(json.dumps(data))
            result = run_checks(load_gates(path), root, root / "timeout")
            self.assertEqual(result["status"], "timeout")
            self.assertEqual(len(result["checks"]), 1)
            data["checks"][0]["argv"] = ["agentlean-nonexistent-check-binary"]
            path.write_text(json.dumps(data))
            self.assertEqual(run_checks(load_gates(path), root, root / "error")["status"], "error")

    def test_distinct_presets_and_missing_repairs_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decision, _ = prepare(root)
            configure(
                root,
                agent="codex",
                tier="balanced",
                model=decision["model"],
                effort=decision["effort"],
            )
            self.assertEqual([p["tier"] for p in repair_plans(decision, 2)], ["fast", "deep"])
            config = json.loads((root / ".agentlean/routing.json").read_text())
            del config["agents"]["codex"]["deep"]
            (root / ".agentlean/routing.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "repair requires"):
                repair_plans(decision, 2)
            with self.assertRaisesRegex(ValueError, "routing on"):
                repair_plans(plan(root, "codex", "Task", routing="off"), 1)
            with self.assertRaises(ValueError):
                repair_plans(decision, 3)

    def test_invalid_gate_definitions(self):
        bad = [
            [],
            {},
            {"schema_version": 1, "checks": []},
            {"schema_version": 1, "checks": [{"name": "x", "argv": "shell command"}]},
            {
                "schema_version": 1,
                "checks": [{"name": "x", "argv": ["python"], "timeout_seconds": -1}],
            },
            {"schema_version": 1, "checks": [{"name": "x", "argv": ["python"]}] * 2},
            {"schema_version": 1, "checks": [{"name": "", "argv": ["python"]}]},
            {"schema_version": 1, "checks": [{"name": "x"}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checks.json"
            for value in bad:
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    load_gates(path)


class QualityCLITests(unittest.TestCase):
    invoke = support.CLITests.invoke

    def test_preview_runs_nothing_and_checked_execution_propagates_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, gates = prepare(root)
            args = [
                "run",
                "--target",
                directory,
                "--agent",
                "codex",
                "--task",
                "Fix typo",
                "--checks",
                str(gates.path),
            ]
            with patch(
                "agentlean.cli.execute_checked",
                return_value=(4, {"status": "checks_failed", "report_path": "report.json"}),
            ) as checked:
                code, output, _ = self.invoke(args)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output)["tier"], "fast")
                checked.assert_not_called()
                self.assertEqual(self.invoke([*args, "--execute"])[0], 4)
            self.assertEqual(self.invoke(args[:-2] + ["--repair-attempts", "1"])[0], 2)
