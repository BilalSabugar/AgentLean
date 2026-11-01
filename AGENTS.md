# AgentLean development

AgentLean is a portable workflow and measurement toolkit. Preserve correctness
while reducing unnecessary context, tool calls and rework. Efficiency claims
require observed, comparable trials; fixtures and demonstrations are not results.

Use Python 3.11+ and the standard library for runtime code. Run
`python -m unittest discover -s tests -v` after behavior changes. Run the CLI with
`python -m agentlean`. Keep installation opt-in, local to the selected repository,
and preserve existing instructions and configuration.

For documentation changes, run `python scripts/check_docs.py`. Public source is
allowlisted by the documentation/export scripts; keep examples and relative links
valid and exclude local logs, private handoffs and development dependencies.

Historical engineering input archives may be present locally as reference
material and are excluded from public source. Preserve them if present.
Implement the general toolkit in `agentlean/`. Domain checks remain important
when applicable.
