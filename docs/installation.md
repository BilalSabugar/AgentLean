# Installation and workflow lifecycle

## Requirements

- Python 3.11+ for the CLI, measurement and workflow installer.
- An existing local project directory for workflow installation and runs.
- A native Codex or Claude Code CLI on PATH only when using `run --execute`.
- Account access and compatible model/effort presets for routed executions.

Previews, workflow installation and manual trial reports do not require provider
credentials or a client installation. AgentLean does not install or sign in to
agent clients. Its runtime uses no third-party Python packages.

## Install from source

Clone/download this repository, enter its directory, and create a local environment.
Use the executable paths below to avoid relying on shell activation.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/agentlean --version
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\agentlean.exe --version
```

If `python`, `python3` or `py` is unavailable, use the full path to your installed
Python 3.11+ interpreter. A Windows Store execution alias is not necessarily a
working interpreter. No PATH, registry or execution-policy changes are required.

For contributing, replace `pip install .` with `pip install -e ".[dev]"`. For a
locally built wheel, run the environment's Python with
`-m pip install /path/to/agentlean-VERSION-py3-none-any.whl`. The filename is a
placeholder: use the versioned artifact you actually inspected. Registry
publication is not established; `pip install agentlean` is not the source-install
instruction for this project.

From an uninstalled checkout you can always use `python -m agentlean` in place of
`agentlean`. In the commands below, use the executable inside your environment if
it is not activated.

## Install into a project

```sh
agentlean init /path/to/project --agent codex
agentlean init /path/to/project --agent codex --apply
```

The first command previews. The target must already exist. Profiles create:

| Profile | Workflow | Instructions added only if absent |
| --- | --- | --- |
| codex | `.agents/skills/agentlean/SKILL.md` | `AGENTS.md` |
| claude | `.claude/skills/agentlean/SKILL.md` | `CLAUDE.md` |
| generic | `.agentlean/workflow.md` | `AGENTS.md` |

Existing instructions remain user-owned. Merge the
[instruction fragment](../agentlean/templates/AGENTS.md) manually if useful.
Ownership and SHA256 hashes are recorded in `.agentlean/install-PROFILE.json`.
Repeating an unchanged managed install is safe; unowned or edited workflow files
stop the operation rather than being overwritten. No personal client settings
are changed.

Invoke `$agentlean` in Codex or `/agentlean` in Claude Code. For another agent,
explicitly load `.agentlean/workflow.md`. These are instruction layouts, not a
claim that every client version has been exercised. Review your client's native
skill mechanism if the workflow is not discovered.

## Upgrade or remove

Install the desired AgentLean release in your environment, then preview:

```sh
agentlean init /path/to/project --agent codex --upgrade
agentlean uninstall /path/to/project --agent codex
```

Add `--apply` after reviewing the output. Upgrades and removal require unchanged
managed files. Back up custom edits and restore the recorded version before
continuing; do not delete the ownership manifest to bypass a conflict. Removal
preserves pre-existing instructions, routing settings, trial data and quality logs.
Empty directories and harmless persistent lock files remain.

Version 0.1 prototype installs have no ownership manifest. Move the generated
workflow aside before installing a current release. Existing instructions remain
user-owned; no implicit adoption or destructive migration occurs.

## Recover interrupted operations

```sh
agentlean recover /path/to/project
agentlean recover /path/to/project --apply
```

Ordinary I/O failures attempt rollback. An interrupted operation leaves recovery
data in `.agentlean/install-transaction.json`. Recovery previews restoration of
the preceding state and stops if a file has since been edited. Keep a backup
before resolving a conflict. See [troubleshooting](troubleshooting.md) for logs,
locks and model-routing failures.
