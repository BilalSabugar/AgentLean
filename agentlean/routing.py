"""Opt-in task routing and per-invocation Codex/Claude model overrides."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .storage import atomic_write, file_lock, strict_json

AGENTS = ("codex", "claude")
TIERS = ("fast", "balanced", "deep")
EFFORTS = {
    "codex": ("native", "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"),
    "claude": ("native", "low", "medium", "high", "xhigh", "max", "ultracode"),
}
RISK = re.compile(
    r"\b(security|auth(?:entication|orization)?|payment[s]?|cryptograph\w*|"
    r"production|migrat\w*|delete|destructive|safety|medical|firmware|motor[s]?|mains)\b",
    re.I,
)
COMPLEX = re.compile(
    r"\b(architect\w*|refactor\w*|concurren\w*|deadlock|race condition|"
    r"distributed|multi[- ](?:file|step|service)|redesign|debug\w*|investigate)\b",
    re.I,
)
SIMPLE = re.compile(r"\b(typo[s]?|spelling|punctuation|formatting|rename a variable)\b", re.I)
IMPLEMENTATION = re.compile(
    r"\b(implement\w*|add|build|creat\w*|logic|behavio[u]?r|algorithm|endpoint|"
    r"optimiz\w*|performance|review|explain|analy\w*|test\w*)\b",
    re.I,
)


def _location(target: Path) -> tuple[Path, Path]:
    root = target.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("target must be an existing repository directory")
    path = root / ".agentlean/routing.json"
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError("routing configuration escapes target or is a symlink")
    return root, path


def _validate(config: dict) -> dict:
    if (
        not isinstance(config, dict)
        or set(config) != {"schema_version", "enabled", "agents"}
        or type(config["schema_version"]) is not int
        or config["schema_version"] != 1
        or type(config["enabled"]) is not bool
        or not isinstance(config["agents"], dict)
        or not set(config["agents"]).issubset(AGENTS)
    ):
        raise ValueError("invalid routing configuration schema")
    for agent, presets in config["agents"].items():
        if not isinstance(presets, dict) or not set(presets).issubset(TIERS):
            raise ValueError(f"invalid routing tiers for {agent}")
        for preset in presets.values():
            if not isinstance(preset, dict) or set(preset) != {"model", "effort"}:
                raise ValueError("each routing preset requires model and effort")
            model, effort = preset["model"], preset["effort"]
            if (
                not isinstance(model, str)
                or not model.strip()
                or model != model.strip()
                or model.startswith("-")
                or any(ord(c) < 32 or ord(c) == 127 for c in model)
            ):
                raise ValueError(
                    "model must be a nonempty identifier without flags or control characters"
                )
            if effort not in EFFORTS[agent]:
                raise ValueError(
                    f"unsupported {agent} effort; choose from {', '.join(EFFORTS[agent])}"
                )
    return config


def settings(target: Path) -> dict:
    _, path = _location(target)
    if not path.exists():
        return {"schema_version": 1, "enabled": False, "agents": {}}
    return _validate(strict_json(path.read_text(encoding="utf-8")))


def configure(
    target: Path,
    enabled: bool | None = None,
    *,
    agent: str | None = None,
    tier: str | None = None,
    model: str | None = None,
    effort: str = "native",
) -> dict:
    _, path = _location(target)
    lock = path.with_name("routing.lock")
    if lock.is_symlink():
        raise ValueError("routing lock must not be a symlink")
    with file_lock(lock):
        config = settings(target)
        if enabled is not None:
            if type(enabled) is not bool:
                raise ValueError("routing enabled must be a boolean")
            config["enabled"] = enabled
        if agent is not None:
            if agent not in AGENTS or tier not in TIERS:
                raise ValueError("choose a supported agent and routing tier")
            config["agents"].setdefault(agent, {})[tier] = {"model": model, "effort": effort}
        _validate(config)
        atomic_write(path, (json.dumps(config, indent=2) + "\n").encode("utf-8"))
        return config


def select_tier(
    task: str, complexity: str = "auto", risk: str = "normal", failed_attempts: int = 0
):
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be nonempty")
    if complexity not in ("auto", "simple", "standard", "complex") or risk not in (
        "normal",
        "high",
    ):
        raise ValueError("invalid complexity or risk")
    if type(failed_attempts) is not int or failed_attempts < 0:
        raise ValueError("failed_attempts must be a nonnegative integer")
    if risk == "high" or RISK.search(task):
        return "deep", "higher-risk task; use the configured deep tier"
    if complexity == "complex" or (complexity == "auto" and COMPLEX.search(task)):
        return "deep", "complex task; use the configured deep tier"
    if complexity == "simple" or (
        complexity == "auto"
        and len(task) <= 300
        and SIMPLE.search(task)
        and not IMPLEMENTATION.search(task)
    ):
        level, reason = 0, "simple task"
    else:
        level, reason = 1, "standard or uncertain task"
    if failed_attempts:
        level = min(2, level + failed_attempts)
        reason += f"; escalated after {failed_attempts} reported failed attempt(s)"
    return TIERS[level], reason


def plan(
    target: Path,
    agent: str,
    task: str,
    complexity: str = "auto",
    risk: str = "normal",
    failed_attempts: int = 0,
    routing: str = "inherit",
    has_checks: bool = False,
) -> dict:
    root, _ = _location(target)
    if agent not in AGENTS or routing not in ("inherit", "on", "off"):
        raise ValueError("invalid agent or routing override")
    tier, reason = select_tier(task, complexity, risk, failed_attempts)
    config = settings(root)
    enabled = config["enabled"] if routing == "inherit" else routing == "on"
    if tier == "fast" and not has_checks:
        tier, reason = "balanced", "fast tier requires acceptance checks; use balanced without them"
    result = {
        "agent": agent,
        "target": str(root),
        "routing_enabled": enabled,
        "tier": None,
        "model": None,
        "effort": "native",
        "reason": "routing off; preserve client defaults",
    }
    if enabled:
        preset = config["agents"].get(agent, {}).get(tier)
        if preset is None:
            raise ValueError(
                f"no {agent}/{tier} preset; configure it with routing set before launching"
            )
        result.update(tier=tier, reason=reason, **preset)
    result["argv"] = command(result)
    result["prompt_transport"] = "stdin (task text omitted from preview)"
    return result


def repair_plans(decision: dict, maximum: int) -> list[dict]:
    """Snapshot distinct stronger presets before spending on the first run."""
    if type(maximum) is not int or not 0 <= maximum <= 2:
        raise ValueError("repair attempts must be between 0 and 2")
    if maximum and not decision["routing_enabled"]:
        raise ValueError("automatic escalation requires routing on")
    attempts = [decision]
    seen = {(decision["model"], decision["effort"])}
    if maximum:
        config = settings(Path(decision["target"]))
        for tier in TIERS[TIERS.index(decision["tier"]) + 1 :]:
            preset = config["agents"].get(decision["agent"], {}).get(tier)
            if preset is None:
                raise ValueError(f"repair requires a configured {decision['agent']}/{tier} preset")
            identity = (preset["model"], preset["effort"])
            if identity in seen:
                continue
            seen.add(identity)
            updated = {
                **decision,
                **preset,
                "tier": tier,
                "reason": "escalation after a failed acceptance check",
            }
            updated["argv"] = command(updated)
            attempts.append(updated)
            if len(attempts) - 1 == maximum:
                break
    return attempts


def command(decision: dict) -> list[str]:
    agent = decision["agent"]
    arguments = [agent, "exec"] if agent == "codex" else [agent, "-p"]
    if decision["model"] is not None:
        arguments.extend(["--model", decision["model"]])
    if decision["effort"] != "native":
        if agent == "codex":
            arguments.extend(["-c", "model_reasoning_effort=" + json.dumps(decision["effort"])])
        else:
            arguments.extend(["--effort", decision["effort"]])
    if agent == "codex":
        arguments.append("-")
    return arguments


def launch(decision: dict, task: str) -> int:
    """Start one native client run, preserving its permissions and exit status."""
    executable = shutil.which(decision["agent"])
    if executable is None:
        raise ValueError(f"{decision['agent']} CLI is not on PATH; preview works without it")
    if os.name == "nt" and Path(executable).suffix.lower() in (".cmd", ".bat"):
        raise ValueError("use a native .exe CLI on Windows; batch wrappers are not supported")
    arguments = [executable, *command(decision)[1:]]
    completed = subprocess.run(
        arguments,
        input=task,
        text=True,
        encoding="utf-8",
        cwd=decision["target"],
        check=False,
        shell=False,
    )
    return completed.returncode if completed.returncode >= 0 else 128 - completed.returncode
