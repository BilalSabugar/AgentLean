# AgentLean

**Less overhead. More output. Keep the quality checks.**

AgentLean is an MIT-licensed toolkit for focused AI-agent work. It combines a
portable workflow, optional model and reasoning routing for Codex and Claude Code,
task acceptance checks, and local experiment tracking.

Use it to reduce avoidable context, repeated attempts and unnecessary model calls
while keeping verification explicit. It works across software, documentation,
data and engineering tasks; specialist validation remains your responsibility.

**Status: 0.4.0, early release.** Windows checks pass on Python 3.11 and 3.14.
Linux/macOS CI is configured but has not run remotely. Live agent-client behavior
and real-world efficiency gains remain unverified. AgentLean does not change
model capabilities, subscription limits or provider accounting.

## Quick start

Download or clone this source repository and open a terminal in its directory.
Python 3.11+ is required. Try the CLI directly, without installing dependencies:

```sh
python -m agentlean --help
python -m agentlean routing status
```

For regular use, [install into a virtual environment](docs/installation.md), then
preview the workflow installation in an existing project:

```sh
agentlean init /path/to/project --agent codex
agentlean init /path/to/project --agent codex --apply
```

`/path/to/project` is a placeholder. Choose `claude` or `generic` for another
profile. Preview writes nothing; `--apply` creates managed project files.
Existing instructions, user edits and personal agent settings are preserved.

This project has not published a registry package. Install from this checkout or an
inspected release wheel; do not assume a similarly named registry package is this
project. The CLI's runtime and test suite use the Python standard library.

## What it does

| Capability | Behavior |
| --- | --- |
| Portable workflow | Focused discovery, hypothesis-driven debugging, targeted checks and concise handoffs |
| Optional routing | Your fast, balanced and deep model/effort presets; off by default |
| Acceptance gates | Baseline before model spend, then post-run checks before a verified result |
| Bounded repair | Explicit opt-in escalation after failed checks; duplicate presets and repeated diagnostics stop retries |
| Managed installation | Preview, repeatable install, explicit upgrades/removal and interruption recovery |
| Local measurement | Manually observed trials and conservative matched-pair reports |

Routing applies to **new AgentLean-launched CLI runs**, not already-open desktop
chats. Native client authentication and permissions still apply. A configured
preset does not prove that your account supports that model or reasoning level.

## Model routing: on or off

First [configure account-valid presets](docs/model-routing.md) for the clients you
use. You can vary the model, reasoning effort, or both.

```sh
agentlean routing on
agentlean routing status
agentlean run --agent codex --task "Implement pagination"
agentlean routing off
```

`run` previews its decision by default. Add `--execute` to send the task to the
installed native client. Off omits AgentLean's model/effort overrides. Uncertain
work defaults to balanced; complex and higher-risk signals use deep. Fast routing
requires explicit acceptance checks.

## Protect the output

Define task-specific checks using [the example format](examples/checks.python.json),
then review the preview before executing:

```sh
agentlean run --agent codex --task "Fix parser behavior" --checks checks.json
agentlean run --agent codex --task "Fix parser behavior" --checks checks.json --execute
```

The example is a starting point: replace its commands with checks that actually
cover your task. A broken baseline stops before a model call. A zero client exit
cannot hide failing acceptance checks. Optional `--repair-attempts 1` allows one
additional distinct stronger-preset run after validation fails; it never retries
an authentication or other native client error.

Checks execute explicitly supplied local commands. Full logs and checkpointed
reports stay under `.agentlean/runs/`. Passing checks establishes those criteria,
not universal correctness. Read [quality gates](docs/quality-gates.md) and
[security/data handling](SECURITY.md) before running or sharing evidence.

## Measure results honestly

Record actual baseline and AgentLean runs on equivalent tasks, environments and
acceptance criteria, including failures. Use `agentlean trial`, `agentlean check`
and `agentlean report` to validate observations and compare matched pairs.

The tool does not automatically read provider usage or treat allowance percentages
across providers as equivalent tokens. Tests and example data are not performance
benchmarks. See [the measurement protocol](docs/measurement.md).

## Documentation

- [Documentation index](docs/README.md) and [installation](docs/installation.md)
- [CLI reference](docs/cli.md), [model routing](docs/model-routing.md) and [quality gates](docs/quality-gates.md)
- [Examples](examples/README.md), [troubleshooting](docs/troubleshooting.md) and [FAQ](docs/faq.md)
- [Architecture](docs/architecture.md), [roadmap](docs/roadmap.md) and [changelog](CHANGELOG.md)
- [Local validation evidence](docs/release-validation.md) and [release procedure](docs/releasing.md)

## Contribute

Bug reproductions, documentation fixes, meaningful tests and sanitized matched-task
experiments are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md),
[the code of conduct](CODE_OF_CONDUCT.md) and [governance](GOVERNANCE.md).

```sh
python -m unittest discover -s tests -v
python scripts/check_docs.py
```

For usage help see [SUPPORT.md](SUPPORT.md). Security reports belong in the private
reporting channel described in [SECURITY.md](SECURITY.md), not a public bug report.

## License and provenance

Licensed under the [MIT License](LICENSE). See [NOTICE.md](NOTICE.md) for provenance
and third-party documentation references. AgentLean is independent of OpenAI,
Anthropic and other agent vendors. Local development material and private handoffs
are excluded from the public source bundle.
