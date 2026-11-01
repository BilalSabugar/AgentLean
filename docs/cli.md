# CLI reference

Use `agentlean --help` or `agentlean COMMAND --help` for authoritative syntax.
`python -m agentlean` is equivalent from a checkout or installed environment.
Paths containing spaces must be quoted in your shell.

| Command | Purpose | Default behavior |
| --- | --- | --- |
| `init [TARGET] --agent codex\|claude\|generic` | Install/update repository workflow | Preview; add `--apply` to write, `--upgrade` to update unchanged owned files |
| `uninstall [TARGET] --agent PROFILE` | Remove owned workflow | Preview; add `--apply` |
| `recover [TARGET]` | Roll back an interrupted install | Preview; add `--apply` |
| `routing [--target TARGET] status` | Read routing settings | No files created |
| `routing [--target TARGET] on` or `off` | Persist the routing toggle | Writes local settings; preserves presets |
| `routing [--target TARGET] set ...` | Set a model/effort preset | Requires `--agent`, `--tier`, `--model`; effort defaults to native |
| `run ...` | Plan or execute a client task | Preview; add `--execute` |
| `trial ...` | Record a manually observed run | Writes a validated JSONL record |
| `check [--file PATH]` | Validate the trial log | No repair or mutation |
| `report [--file PATH] [--output PATH]` | Summarize matched trials | Prints JSON, or atomically writes `--output` |

`TARGET` defaults to the current directory. Routing's `--target` appears before
its operation: `agentlean routing --target /path/to/project on`.

## Run flags

- `--agent codex|claude` and `--task TEXT` are required; `--task -` reads stdin.
- `--target DIR` chooses the working directory and local routing configuration.
- `--complexity auto|simple|standard|complex` supplies a routing hint.
- `--risk normal|high` supplies a risk floor; detected higher-risk signals also
  retain deep routing.
- `--failed-attempts N` reports prior failures and influences the starting tier.
- `--routing inherit|on|off` overrides the saved toggle for this invocation only.
- `--checks PATH` loads explicit acceptance commands. Relative paths resolve
  from the invoking shell, not from `--target`.
- `--repair-attempts 0|1|2` bounds additional stronger-preset runs; default zero.
- `--allow-failing-baseline` permits an intentionally red baseline, not failed
  post-run checks or infrastructure errors.
- `--execute` starts the native client and any supplied acceptance commands.

See [model routing](model-routing.md) and [quality gates](quality-gates.md) for
selection rules, preset requirements and the meaning of a verified result.

## Trial fields

Required: `--task`, `--agent`, `--model`, `--effort`, `--pair`, `--revision`,
`--environment`, `--criteria`, `--variant baseline|lean`, `--result pass|fail|blocked`,
and `--minutes`. A passing result also requires at least one `--evidence` value.

Optional: repeatable `--evidence`, `--iterations`, `--corrections`, `--notes`,
and `--file` (default `.agentlean/trials.jsonl`). Usage observations require both
`--allowance-before-pct` and `--allowance-after-pct`, plus `--allowance-scope`.
See [measurement](measurement.md) for experiment design and interpretation.

## Exit codes and outputs

| Code | Meaning |
| --- | --- |
| 0 | CLI operation succeeded; checked executions additionally require `checks_passed` |
| 2 | Invalid arguments, configuration, filesystem or process-start error |
| 4 | Quality gate blocked completion |
| 130 | Interrupted execution |
| Native client code | Native execution failed; propagated rather than automatically retried |

A native client can itself return 2 or 4. Use its output and the checked-run JSON
status to distinguish that from an AgentLean configuration or validation failure.
An unguarded native exit of zero is labeled unverified, not a quality verdict.

Run previews and trial reports are JSON. Execution previews and checked-run
summaries go to stderr; native client output streams normally. Full check logs
and reports remain under `.agentlean/runs/`. Manual logs, routing configuration
and quality evidence are described in [architecture](architecture.md).
