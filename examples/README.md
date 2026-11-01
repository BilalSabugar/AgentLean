# Examples

These are starting points, not proof that a task is correctly specified or that
AgentLean saves usage. Review commands before running them in your project.

| File | Intended use |
| --- | --- |
| [checks.python.json](checks.python.json) | A project using standard-library unittest discovery |
| [checks.agentlean.json](checks.agentlean.json) | Acceptance checks for this source repository |
| [task-brief.md](task-brief.md) | A concise task with scope and observable completion criteria |

For a Python project, copy or adapt the checks file, then preview from that
project's directory:

```sh
agentlean run --agent codex --task "Fix parser behavior" --checks /path/to/checks.json
```

Add `--execute` only after reviewing the selected preset and trusted commands.
The file path is a placeholder; relative check paths use the invoking shell's
working directory. `{python}` resolves to AgentLean's interpreter. If your project
has another environment, use its interpreter explicitly in the manifest.

The examples use no model IDs, credentials or provider requests. Configure actual
account-valid presets using [model routing](../docs/model-routing.md). A filename
and a passing command cannot establish meaningful acceptance coverage by
themselves; see [quality gates](../docs/quality-gates.md).
