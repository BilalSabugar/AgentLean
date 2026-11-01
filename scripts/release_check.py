"""Test a built wheel in a clean venv, with no source checkout on sys.path.

All recorded observations below are synthetic, isolated test data.
"""

import argparse
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    if wheel.is_dir():
        wheels = list(wheel.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("expected exactly one candidate wheel in directory")
        wheel = wheels[0]
    environment = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    environment["PIP_CONFIG_FILE"] = os.devnull
    with tempfile.TemporaryDirectory(prefix="agentlean-release-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root / "venv")
        scripts = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        executable = scripts / ("agentlean.exe" if os.name == "nt" else "agentlean")
        # A broken guard must fail the test, never reach a real provider client.
        environment["PATH"] = str(scripts)

        def run(*arguments, expected=0):
            completed = subprocess.run(
                [str(a) for a in arguments],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.returncode != expected:
                raise RuntimeError(
                    f"command failed ({completed.returncode}): {arguments}\n"
                    f"{completed.stdout[-4000:]}\n{completed.stderr[-4000:]}"
                )
            return completed.stdout

        run(python, "-m", "pip", "install", "--no-index", "--no-deps", wheel)
        version = run(executable, "--version").strip()
        require(
            run(python, "-m", "agentlean", "--version").strip() == version,
            "entrypoint version mismatch",
        )
        repository = root / "example repository"
        repository.mkdir()
        instructions = repository / "AGENTS.md"
        instructions.write_text("Existing user instructions\n", encoding="utf-8")
        run(executable, "init", repository)
        require(
            sorted(p.name for p in repository.iterdir()) == ["AGENTS.md"], "preview wrote files"
        )
        run(executable, "init", repository, "--apply")
        require(
            "UNCHANGED" in run(executable, "init", repository, "--apply"),
            "repeat install was not idempotent",
        )
        skill = repository / ".agents/skills/agentlean/SKILL.md"
        require(skill.is_file(), "installed workflow missing")
        log = repository / ".agentlean/trials.jsonl"
        common = [
            executable,
            "trial",
            "--file",
            log,
            "--task",
            "synthetic-release-test",
            "--agent",
            "codex",
            "--model",
            "test-model",
            "--effort",
            "none",
            "--pair",
            "1",
            "--revision",
            "fixture-v1",
            "--environment",
            "isolated",
            "--criteria",
            "fixture-checks",
            "--result",
            "pass",
            "--evidence",
            "synthetic package smoke test",
        ]
        run(*common, "--variant", "baseline", "--minutes", "12")
        run(*common, "--variant", "lean", "--minutes", "9")
        run(*common, "--variant", "lean", "--minutes", "9", expected=2)
        run(executable, "check", "--file", log)
        status = json.loads(run(executable, "routing", "--target", repository, "status"))
        require(not status["enabled"], "routing should default off")
        require(not (repository / ".agentlean/routing.json").exists(), "status wrote settings")
        for agent in ("codex", "claude"):
            for tier, effort in zip(
                ("fast", "balanced", "deep"), ("low", "medium", "high"), strict=True
            ):
                run(
                    executable,
                    "routing",
                    "--target",
                    repository,
                    "set",
                    "--agent",
                    agent,
                    "--tier",
                    tier,
                    "--model",
                    f"test-{agent}-{tier}",
                    "--effort",
                    effort,
                )
        run(executable, "routing", "--target", repository, "on")
        gates = repository / "checks.json"
        gates.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "checks": [
                        {"name": "fixture", "argv": ["{python}", "-c", "raise SystemExit(0)"]}
                    ],
                }
            )
        )
        for agent in ("codex", "claude"):
            preview = json.loads(
                run(
                    executable,
                    "run",
                    "--target",
                    repository,
                    "--agent",
                    agent,
                    "--task",
                    "Fix typo in README",
                    "--checks",
                    gates,
                )
            )
            require(preview["model"] == f"test-{agent}-fast", "fast routing failed")
            require(preview["effort"] == "low", "effort routing failed")
        gates.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "checks": [
                        {"name": "red fixture", "argv": ["{python}", "-c", "raise SystemExit(1)"]}
                    ],
                }
            )
        )
        run(
            executable,
            "run",
            "--target",
            repository,
            "--agent",
            "codex",
            "--task",
            "Fix typo",
            "--checks",
            gates,
            "--execute",
            expected=4,
        )
        quality_reports = list((repository / ".agentlean/runs").glob("*/report.json"))
        require(len(quality_reports) == 1, "missing baseline report")
        quality_result = json.loads(quality_reports[0].read_text())
        require(
            quality_result["status"] == "baseline_failed" and not quality_result["attempts"],
            "failed baseline should prevent a model request",
        )
        run(executable, "routing", "--target", repository, "off")
        preview = json.loads(
            run(
                executable,
                "run",
                "--target",
                repository,
                "--agent",
                "codex",
                "--task",
                "Refactor workers",
            )
        )
        require(
            preview["model"] is None and "--model" not in preview["argv"],
            "off switch leaked an override",
        )
        report = root / "report.json"
        run(executable, "report", "--file", log, "--output", report)
        group = json.loads(report.read_text())["groups"][0]
        require(group["matched_pairs"] == 1, "expected one matched pair")
        require(group["time_reduction"]["median_pct"] == 25, "incorrect synthetic comparison")
        original = log.read_bytes()
        run(executable, "report", "--file", log, "--output", log, expected=2)
        require(log.read_bytes() == original, "report modified source log")
        run(executable, "uninstall", repository)
        require(skill.is_file(), "uninstall preview removed workflow")
        run(executable, "uninstall", repository, "--apply")
        require(not skill.exists(), "uninstall left managed workflow")
        require(
            instructions.read_text() == "Existing user instructions\n", "user instructions changed"
        )
        require(log.read_bytes() == original, "uninstall modified trial data")
        print(f"AgentLean {version}: isolated wheel lifecycle and trial checks passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    check(parser.parse_args().wheel)
