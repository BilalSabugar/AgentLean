# Troubleshooting

Start with `agentlean --version`, `python --version` and the exact command that
failed. Preserve the first useful error and a small sanitized excerpt; avoid
posting complete logs, credentials or private project files.

| Symptom | What to check |
| --- | --- |
| `agentlean` is not found | Use the executable inside your virtual environment, or `python -m agentlean` from the checkout |
| Windows Python alias fails | Use `py` or the full path to an installed Python 3.11+ interpreter; see [installation](installation.md) |
| Target does not exist | Create/select an existing project directory; installation does not invent the target |
| Workflow is unowned | An existing workflow has no AgentLean manifest; move it aside after backing it up rather than forcing an overwrite |
| Managed file modified or missing | Back up edits and restore the recorded version before upgrade/removal; the manifest protects your changes |
| Interrupted installation found | Preview `agentlean recover TARGET`; apply only after reviewing the restoration |
| Routing is on but no preset exists | Configure the selected provider/tier with `routing set`; fast without checks moves to balanced |
| Invalid model/effort at launch | Choose a combination supported by the installed client and your account; AgentLean does not query availability |
| Native client absent | Previews work without it; execution needs a native client on PATH and its own authentication |
| Native client rejects the project | Follow that client's trust/repository setup; AgentLean does not bypass its protections |
| Baseline fails before a model call | Fix environment problems, or use `--allow-failing-baseline` for an intentional failing reproduction |
| Client exits zero but run fails | Inspect the quality report: acceptance checks, timeout or manifest integrity blocked success |
| Repair does not happen | It is off by default, requires routing/checks, and stops at deep, duplicates, repeated diagnostics or infrastructure failures |
| A lock sidecar remains | Its presence alone is harmless; OS locks release when the process exits |
| Lock wait times out | Another AgentLean writer may still be active; do not remove the sidecar to bypass it |
| Corrupt/truncated trial log | Run `agentlean check --file PATH`, back up the log, then inspect and explicitly repair the reported line |
| Reports show unmatched runs | Task, pair, agent, model, effort, revision, environment, criteria and usage scope must match |
| Report output path is rejected | Choose a new file, not the source trial log, its lock sidecar or an alias |

Use [SUPPORT.md](../SUPPORT.md) for usage questions and public bug reports.
Use [SECURITY.md](../SECURITY.md) for potential vulnerabilities.
