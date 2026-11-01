---
name: agentlean
description: Execute multi-step repository tasks with focused context, hypothesis-driven recovery, targeted verification, and resumable handoffs. Use for substantial implementation or diagnosis, not trivial edits.
---

# AgentLean

Agree on an observable outcome from the user's request. Inspect the working tree
and locate the smallest relevant set of sources and checks. Follow repository
conventions and load specialist guidance only when the task needs it.

Implement a complete, focused change. Choose checks that can detect meaningful
failures, starting with the cheapest useful check. Expand verification when the
change or a failure warrants it. Keep large generated artifacts and full logs on
disk; bring actionable excerpts into context.

When a command fails, use its error to choose a new hypothesis or intervention.
Don't repeat an unchanged command without evidence of a transient failure.
Keep unresolved failures visible rather than suppressing checks.

When changing subsystems or handing off, retain only the objective, decisions,
modified paths, actual verification, blockers and next action. Reuse an existing
project state note; create one only when continuity benefits. A new chat is an
option, not an automatic requirement.

Report verified outputs and remaining uncertainty. Preserve the user's scope,
selected model, permissions and unrelated changes. Never trade correctness for
usage targets or infer physical validation from generated files.

For efficiency experiments, use AgentLean's trial CLI and measurement protocol
in the toolkit repository. Record real observations; do not infer subscription
usage from message length or compare allowance percentages across providers.
