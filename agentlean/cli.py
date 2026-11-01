"""Local workflow CLI with explicit opt-in native client execution."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .install import install, recover
from .quality import execute as execute_checked
from .quality import load_gates
from .routing import AGENTS, TIERS, configure, launch, plan, repair_plans, settings
from .storage import atomic_write
from .trials import Trial, load_trials, record_trial, summarize


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="agentlean")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="preview an additive repository workflow installation")
    init.add_argument("target", type=Path, nargs="?", default=Path.cwd())
    init.add_argument("--agent", choices=("codex", "claude", "generic"), default="codex")
    init.add_argument(
        "--apply",
        action="store_true",
        help="apply installation; edited or unowned files are preserved",
    )
    init.add_argument(
        "--upgrade", action="store_true", help="update unchanged managed files to this release"
    )
    uninstall = commands.add_parser("uninstall", help="preview removal of unchanged managed files")
    uninstall.add_argument("target", type=Path, nargs="?", default=Path.cwd())
    uninstall.add_argument("--agent", choices=("codex", "claude", "generic"), default="codex")
    uninstall.add_argument("--apply", action="store_true")
    recovery = commands.add_parser(
        "recover", help="preview rollback of an interrupted installation"
    )
    recovery.add_argument("target", type=Path, nargs="?", default=Path.cwd())
    recovery.add_argument("--apply", action="store_true")
    trial = commands.add_parser("trial", help="record one manually observed task run")
    trial.add_argument("--file", type=Path, default=Path(".agentlean/trials.jsonl"))
    for name in ("task", "agent", "model", "effort", "pair", "revision", "environment", "criteria"):
        trial.add_argument("--" + name, required=True)
    trial.add_argument("--variant", choices=("baseline", "lean"), required=True)
    trial.add_argument("--result", choices=("pass", "fail", "blocked"), required=True)
    trial.add_argument("--minutes", type=float, required=True)
    trial.add_argument("--evidence", action="append", default=[])
    trial.add_argument("--iterations", type=int, default=0)
    trial.add_argument("--corrections", type=int, default=0)
    trial.add_argument("--allowance-before-pct", type=float)
    trial.add_argument("--allowance-after-pct", type=float)
    trial.add_argument("--allowance-scope")
    trial.add_argument("--notes", default="")
    report = commands.add_parser(
        "report", help="show descriptive summaries and matched comparisons as JSON"
    )
    report.add_argument("--file", type=Path, default=Path(".agentlean/trials.jsonl"))
    report.add_argument("--output", type=Path, help="atomically save JSON instead of printing")
    check = commands.add_parser(
        "check", help="validate a trial log without generating a comparison"
    )
    check.add_argument("--file", type=Path, default=Path(".agentlean/trials.jsonl"))
    routing = commands.add_parser(
        "routing", help="toggle model routing and configure local presets"
    )
    routing.add_argument("--target", type=Path, default=Path.cwd())
    operations = routing.add_subparsers(dest="operation", required=True)
    for name in ("on", "off", "status"):
        operations.add_parser(name)
    preset = operations.add_parser("set", help="configure an available model and effort for a tier")
    preset.add_argument("--agent", choices=AGENTS, required=True)
    preset.add_argument("--tier", choices=TIERS, required=True)
    preset.add_argument("--model", required=True)
    preset.add_argument(
        "--effort", default="native", help="provider-supported effort, or native to inherit"
    )
    run = commands.add_parser("run", help="preview a routed client launch; --execute starts it")
    run.add_argument("--target", type=Path, default=Path.cwd())
    run.add_argument("--agent", choices=AGENTS, required=True)
    run.add_argument("--task", required=True, help="task prompt; use - to read from stdin")
    run.add_argument(
        "--complexity", choices=("auto", "simple", "standard", "complex"), default="auto"
    )
    run.add_argument("--risk", choices=("normal", "high"), default="normal")
    run.add_argument("--failed-attempts", type=int, default=0)
    run.add_argument("--routing", choices=("inherit", "on", "off"), default="inherit")
    run.add_argument(
        "--checks", type=Path, help="explicit JSON acceptance checks; required for the fast tier"
    )
    run.add_argument(
        "--repair-attempts",
        type=int,
        choices=(0, 1, 2),
        default=0,
        help="maximum stronger-model repair runs after failed checks (default: zero)",
    )
    run.add_argument(
        "--allow-failing-baseline",
        action="store_true",
        help="allow a known failing baseline when fixing those checks",
    )
    run.add_argument(
        "--execute", action="store_true", help="send task to the installed CLI and start one run"
    )
    return root


def main(argv=None) -> int:
    args = vars(parser().parse_args(argv))
    command = args.pop("command")
    try:
        if command == "routing":
            operation = args.pop("operation")
            if operation == "status":
                config = settings(args["target"])
            elif operation == "set":
                config = configure(**args)
            else:
                config = configure(args["target"], enabled=operation == "on")
            print(json.dumps(config, indent=2))
        elif command == "run":
            execute = args.pop("execute")
            checks = args.pop("checks")
            repairs = args.pop("repair_attempts")
            allow_red = args.pop("allow_failing_baseline")
            if (repairs or allow_red) and checks is None:
                raise ValueError("repair attempts and failing-baseline permission require --checks")
            gates = load_gates(checks) if checks is not None else None
            if args["task"] == "-":
                args["task"] = sys.stdin.read()
            decision = plan(**args, has_checks=gates is not None)
            if gates is not None:
                candidates = repair_plans(decision, repairs)
                decision["quality"] = {
                    "checks_sha256": gates.digest,
                    "checks": [check.name for check in gates.checks],
                    "maximum_client_runs": len(candidates),
                    "allow_failing_baseline": allow_red,
                }
            if execute:
                print(json.dumps(decision), file=sys.stderr, flush=True)
                if gates is not None:
                    code, report = execute_checked(
                        decision, args["task"], gates, repairs, allow_red
                    )
                    print(
                        json.dumps(
                            {
                                "quality_status": report["status"],
                                "report_path": report["report_path"],
                            }
                        ),
                        file=sys.stderr,
                    )
                    return code
                print(
                    "AgentLean: no acceptance checks configured; output is unverified",
                    file=sys.stderr,
                )
                return launch(decision, args["task"])
            print(json.dumps(decision, indent=2))
        elif command == "recover":
            print("\n".join(recover(**args)))
        elif command in ("init", "uninstall"):
            if command == "uninstall":
                args["remove"] = True
            print("\n".join(install(**args)))
        elif command == "trial":
            path = args.pop("file")
            trial = Trial(**args)
            record_trial(path, trial)
            print(f"Recorded {trial.trial_id} in {path}")
        else:
            path = args["file"]
            if not path.is_file():
                raise ValueError(f"trial log does not exist: {path}")
            trials = load_trials(path)
            if command == "check":
                print(f"Valid: {len(trials)} trials in {path}")
            else:
                content = json.dumps(summarize(trials), indent=2, allow_nan=False) + "\n"
                output = args["output"]
                if output is None:
                    print(content, end="")
                else:
                    if output.resolve() in (
                        path.resolve(),
                        path.with_name(path.name + ".lock").resolve(),
                    ) or (output.exists() and output.samefile(path)):
                        raise ValueError("report output must not overwrite the trial log")
                    atomic_write(output, content.encode("utf-8"))
                    print(f"Wrote report to {output}")
    except BrokenPipeError:
        return 0
    except (ValueError, TypeError, OSError, OverflowError) as exc:
        print(f"agentlean: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("agentlean: interrupted", file=sys.stderr)
        return 130
    return 0
