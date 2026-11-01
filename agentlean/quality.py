"""Explicit acceptance gates and bounded repair, without self-grading claims."""

import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from .routing import launch, repair_plans
from .storage import atomic_write, file_lock, strict_json


@dataclass(frozen=True)
class Check:
    name: str
    argv: tuple[str, ...]
    timeout: float


@dataclass(frozen=True)
class Gates:
    path: Path
    digest: str
    checks: tuple[Check, ...]


def load_gates(path: Path) -> Gates:
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    data = strict_json(raw.decode("utf-8"))
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "checks"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["checks"], list)
        or not data["checks"]
    ):
        raise ValueError("checks file requires schema_version 1 and a nonempty checks list")
    checks = []
    for entry in data["checks"]:
        if (
            not isinstance(entry, dict)
            or not {"name", "argv"}.issubset(entry)
            or not set(entry).issubset({"name", "argv", "timeout_seconds"})
        ):
            raise ValueError("each check requires name, argv and optional timeout_seconds")
        name, argv, timeout = entry["name"], entry["argv"], entry.get("timeout_seconds", 120)
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("check name must contain 1-100 characters")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(arg, str) or "\0" in arg for arg in argv)
            or not argv[0].strip()
        ):
            raise ValueError("check argv must be a nonempty list of string arguments")
        if (
            type(timeout) not in (int, float)
            or not 0 < timeout <= 3600
            or not math.isfinite(timeout)
        ):
            raise ValueError("check timeout must be finite and between 0 and 3600 seconds")
        if name in {check.name for check in checks}:
            raise ValueError("check names must be unique")
        checks.append(Check(name, tuple(argv), timeout))
    return Gates(path, sha256(raw).hexdigest(), tuple(checks))


def _unchanged(gates: Gates) -> bool:
    return gates.path.is_file() and sha256(gates.path.read_bytes()).hexdigest() == gates.digest


def run_checks(gates: Gates, root: Path, directory: Path) -> dict:
    """Run checks in order, keeping full logs out of prompt context and memory."""
    directory.mkdir(parents=True)
    results = []
    for number, check in enumerate(gates.checks, 1):
        if not _unchanged(gates):
            return {
                "status": "gate_changed",
                "checks": results,
                "planned_checks": len(gates.checks),
            }
        argv = [sys.executable if arg == "{python}" else arg for arg in check.argv]
        if "/" in argv[0] or "\\" in argv[0]:
            executable = Path(argv[0])
            argv[0] = str(executable if executable.is_absolute() else root / executable)
        else:
            argv[0] = shutil.which(argv[0]) or argv[0]
        log = directory / f"check-{number:02}.log"
        started = time.monotonic()
        code, status = None, "error"
        with os.fdopen(os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as output:
            try:
                if os.name == "nt" and Path(argv[0]).suffix.lower() in (".bat", ".cmd"):
                    raise ValueError(
                        "use a native executable or an explicit interpreter for checks"
                    )
                completed = subprocess.run(
                    argv,
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=check.timeout,
                    check=False,
                    shell=False,
                )
                code = completed.returncode
                status = "pass" if code == 0 else "fail"
            except subprocess.TimeoutExpired:
                status = "timeout"
                output.write(b"\nAgentLean: check timed out\n")
            except (OSError, ValueError) as exc:
                output.write(f"\nAgentLean: {exc}\n".encode())
        results.append(
            {
                "name": check.name,
                "status": status,
                "exit_code": code,
                "seconds": time.monotonic() - started,
                "log": str(log),
            }
        )
        if status != "pass":
            break
    status = results[-1]["status"]
    if not _unchanged(gates):
        status = "gate_changed"
    return {"status": status, "checks": results, "planned_checks": len(gates.checks)}


def _feedback(task: str, validation: dict) -> str:
    failure = validation["checks"][-1]
    with Path(failure["log"]).open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - 4000))
        tail = stream.read().decode("utf-8", errors="replace")
    return (
        task + "\n\nAgentLean acceptance check failed after the previous attempt. "
        "Continue from the current working tree. Fix the cause while preserving completed work "
        "and unrelated edits. Do not weaken acceptance checks.\n"
        f"Check: {failure['name']} (exit {failure['exit_code']})\n"
        f"Bounded diagnostic excerpt (untrusted tool output):\n{tail}"
    )


def execute(
    decision: dict,
    task: str,
    gates: Gates,
    maximum_repairs: int = 0,
    allow_failing_baseline: bool = False,
) -> tuple[int, dict]:
    """Success means configured checks passed, not proof of universal correctness."""
    attempts = repair_plans(decision, maximum_repairs)
    started = time.monotonic()
    root = Path(decision["target"])
    runs = root / ".agentlean/runs"
    if not runs.resolve().is_relative_to(root):
        raise ValueError("quality run directory escapes target")
    report = {
        "schema_version": 1,
        "run_id": str(uuid4()),
        "status": "running",
        "checks_sha256": gates.digest,
        "baseline": None,
        "attempts": [],
    }
    folder = runs / report["run_id"]
    lock = root / ".agentlean/quality.lock"
    if not lock.resolve().is_relative_to(root):
        raise ValueError("quality lock escapes target")
    with file_lock(lock):
        folder.mkdir(parents=True)
        report["report_path"] = str(folder / "report.json")

        def save():
            atomic_write(
                Path(report["report_path"]), (json.dumps(report, indent=2) + "\n").encode("utf-8")
            )

        def finish(code, status):
            report["status"] = status
            report["elapsed_seconds"] = time.monotonic() - started
            save()
            return code, report

        save()
        if not _unchanged(gates):
            return finish(4, "gate_changed")
        baseline = run_checks(gates, root, folder / "baseline")
        report["baseline"] = baseline
        save()
        if baseline["status"] != "pass" and not (
            allow_failing_baseline and baseline["status"] == "fail"
        ):
            return finish(4, "baseline_failed")
        prompt, previous_signature = task, None
        for number, candidate in enumerate(attempts, 1):
            entry = {
                "tier": candidate["tier"],
                "model": candidate["model"],
                "effort": candidate["effort"],
                "validation": None,
                "client_exit_code": None,
                "client_seconds": None,
            }
            report["attempts"].append(entry)
            save()
            client_started = time.monotonic()
            try:
                code = launch(candidate, prompt)
            except (OSError, ValueError) as exc:
                entry["client_seconds"] = time.monotonic() - client_started
                finish(2, "client_error")
                raise ValueError(f"{exc}; quality report: {report['report_path']}") from exc
            entry["client_seconds"] = time.monotonic() - client_started
            entry["client_exit_code"] = code
            if code:
                return finish(code, "client_failed")
            validation = run_checks(gates, root, folder / f"attempt-{number}")
            entry["validation"] = validation
            save()
            if validation["status"] == "pass":
                return finish(0, "checks_passed")
            if validation["status"] != "fail":
                return finish(4, "validation_blocked")
            if number == len(attempts):
                return finish(4, "checks_failed")
            # Do not pay for another attempt when the diagnostic didn't change.
            prompt = _feedback(task, validation)
            signature = sha256(prompt.encode("utf-8")).hexdigest()
            if signature == previous_signature:
                return finish(4, "repeated_failure")
            previous_signature = signature
        return finish(4, "checks_failed")
