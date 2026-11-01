"""Versioned, manually observed trials with conservative matched comparisons."""

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from uuid import uuid4

from .storage import atomic_write, file_lock, strict_json


@dataclass(frozen=True)
class Trial:
    task: str
    agent: str
    model: str
    effort: str
    variant: str
    pair: str
    revision: str
    environment: str
    criteria: str
    result: str
    minutes: float
    evidence: list[str] | tuple[str, ...]
    iterations: int = 0
    corrections: int = 0
    allowance_before_pct: float | None = None
    allowance_after_pct: float | None = None
    allowance_scope: str | None = None
    notes: str = ""
    schema_version: int = 1
    trial_id: str = ""
    observed_at: str = ""

    def __post_init__(self):
        for name in (
            "task",
            "agent",
            "model",
            "effort",
            "pair",
            "revision",
            "environment",
            "criteria",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if self.variant not in ("baseline", "lean"):
            raise ValueError("variant must be baseline or lean")
        if self.result not in ("pass", "fail", "blocked"):
            raise ValueError("result must be pass, fail or blocked")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported trial schema version")
        try:
            valid_minutes = (
                type(self.minutes) in (int, float)
                and math.isfinite(self.minutes)
                and self.minutes >= 0
            )
        except OverflowError:
            valid_minutes = False
        if not valid_minutes:
            raise ValueError("minutes must be finite and nonnegative")
        for name in ("iterations", "corrections"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not isinstance(self.evidence, (list, tuple)) or any(
            not isinstance(x, str) or not x.strip() for x in self.evidence
        ):
            raise ValueError("evidence must be a list of nonempty paths or check descriptions")
        if self.result == "pass" and not self.evidence:
            raise ValueError("passing trials require validation evidence")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        before, after = self.allowance_before_pct, self.allowance_after_pct
        if (before is None) != (after is None):
            raise ValueError("supply both allowance observations or neither")
        if before is not None:
            if any(
                type(x) not in (int, float) or not 0 <= x <= 100 or not math.isfinite(x)
                for x in (before, after)
            ):
                raise ValueError("allowance percentages must be finite and between 0 and 100")
            if after > before:
                raise ValueError(
                    "allowance increased: omit usage for reset/replenishment runs and explain in notes"
                )
            if not isinstance(self.allowance_scope, str) or not self.allowance_scope.strip():
                raise ValueError(
                    "usage requires allowance_scope identifying product, plan and window type"
                )
        elif self.allowance_scope is not None:
            raise ValueError("allowance_scope requires observations")
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        if self.trial_id == "":
            object.__setattr__(self, "trial_id", str(uuid4()))
        if not isinstance(self.trial_id, str) or not self.trial_id.strip():
            raise ValueError("trial_id must be a nonempty string")
        if not isinstance(self.observed_at, str):
            raise ValueError("observed_at must be a timestamp string")
        if self.observed_at == "":
            object.__setattr__(self, "observed_at", datetime.now(UTC).isoformat())
        timestamp = datetime.fromisoformat(self.observed_at)
        if timestamp.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")

    @property
    def match_key(self):
        return (
            self.task,
            self.agent,
            self.model,
            self.effort,
            self.pair,
            self.revision,
            self.environment,
            self.criteria,
            self.allowance_scope,
        )


def load_trials(path: Path) -> list[Trial]:
    if not path.exists():
        return []
    trials = []
    names = {field.name for field in fields(Trial)}
    # Close the file before parsing so Windows readers don't hold up replacement.
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    if lines[-1] == "":
        lines.pop()
    for number, line in enumerate(lines, 1):
        try:
            data = strict_json(line)
            if not isinstance(data, dict) or set(data) != names:
                raise ValueError("expected a complete versioned trial record")
            if (
                not isinstance(data["trial_id"], str)
                or not data["trial_id"].strip()
                or not isinstance(data["observed_at"], str)
                or not data["observed_at"].strip()
            ):
                raise ValueError("persisted trial requires identity and timestamp")
            trials.append(Trial(**data))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path}:{number}: invalid trial: {exc}") from exc
    identities = [trial.trial_id for trial in trials]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate trial IDs in log")
    keys = [(trial.match_key, trial.variant) for trial in trials]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate variant within a matched pair; use a new pair ID for repeats")
    return trials


def record_trial(path: Path, trial: Trial) -> None:
    if not isinstance(trial, Trial):
        raise ValueError("expected a validated Trial")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with file_lock(lock):
        previous = load_trials(path)
        if any(
            t.trial_id == trial.trial_id
            or (t.match_key == trial.match_key and t.variant == trial.variant)
            for t in previous
        ):
            raise ValueError("duplicate trial or pair variant; use a new pair ID for repeated runs")
        content = "".join(json.dumps(asdict(t), allow_nan=False) + "\n" for t in [*previous, trial])
        atomic_write(path, content.encode("utf-8"))


def summarize(trials: list[Trial]) -> dict:
    groups = defaultdict(list)
    for trial in trials:
        groups[(trial.agent, trial.model, trial.effort, trial.allowance_scope)].append(trial)
    summaries = []
    for (agent, model, effort, scope), runs in sorted(
        groups.items(), key=lambda item: repr(item[0])
    ):
        variants = {}
        for variant in ("baseline", "lean"):
            selected = [t for t in runs if t.variant == variant]
            observed = [t for t in selected if t.allowance_before_pct is not None]
            used = sum(t.allowance_before_pct - t.allowance_after_pct for t in observed)
            completed = sum(t.result == "pass" for t in observed)
            variants[variant] = {
                "runs": len(selected),
                "passed": sum(t.result == "pass" for t in selected),
                "failed": sum(t.result == "fail" for t in selected),
                "blocked": sum(t.result == "blocked" for t in selected),
                "total_minutes": sum(t.minutes for t in selected),
                "manual_corrections": sum(t.corrections for t in selected),
                "observed_allowance_runs": len(observed),
                "allowance_consumed_pct_points": used if observed else None,
                "verified_completions_per_pct_point": completed / used if used > 0 else None,
            }
        pairs = defaultdict(dict)
        for trial in runs:
            pair = pairs[trial.match_key]
            if trial.variant in pair:
                raise ValueError("ambiguous duplicate pair variant")
            pair[trial.variant] = trial
        time_changes, usage_changes, outcomes = [], [], defaultdict(int)
        complete = 0
        for pair in pairs.values():
            if set(pair) != {"baseline", "lean"}:
                continue
            complete += 1
            base, lean = pair["baseline"], pair["lean"]
            outcomes[f"{base.result}->{lean.result}"] += 1
            if base.result != "pass" or lean.result != "pass":
                continue
            if base.minutes > 0:
                time_changes.append(100 * (base.minutes - lean.minutes) / base.minutes)
            if base.allowance_before_pct is not None and lean.allowance_before_pct is not None:
                baseline_used = base.allowance_before_pct - base.allowance_after_pct
                lean_used = lean.allowance_before_pct - lean.allowance_after_pct
                if baseline_used > 0 and lean_used > 0:
                    usage_changes.append(100 * (baseline_used - lean_used) / baseline_used)

        def describe(values):
            return {
                "n": len(values),
                "median_pct": median(values) if values else None,
                "min_pct": min(values) if values else None,
                "max_pct": max(values) if values else None,
            }

        summaries.append(
            {
                "agent": agent,
                "model": model,
                "effort": effort,
                "allowance_scope": scope,
                "variants": variants,
                "matched_pairs": complete,
                "unmatched_runs": len(runs) - 2 * complete,
                "paired_outcomes": dict(outcomes),
                "time_reduction": describe(time_changes),
                "allowance_reduction": describe(usage_changes),
            }
        )
    return {
        "schema_version": 1,
        "groups": summaries,
        "caveat": "Descriptive observations, not causal proof. Positive reductions favor lean. "
        "Ratios use pairs where both runs passed. Zero usage deltas are excluded as potentially rounded. "
        "Allowance percentages are comparable only within the recorded product/plan/window scope.",
    }
