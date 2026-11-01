# Optional model and reasoning routing

Routing is off by default. When enabled, AgentLean chooses one of your configured
model/effort presets before starting a new Codex CLI or Claude Code run. It does
not replace a running chat's model, change personal client settings, switch
providers, or send classification requests to another LLM.

## Configure available models

Choose model identifiers or aliases available in your account. Configure three
tiers for each client you want to route. The model names below are placeholders,
not published model recommendations:

```sh
agentlean routing set --agent codex --tier fast --model YOUR_FAST_CODEX_MODEL --effort low
agentlean routing set --agent codex --tier balanced --model YOUR_BALANCED_CODEX_MODEL --effort medium
agentlean routing set --agent codex --tier deep --model YOUR_DEEP_CODEX_MODEL --effort high
agentlean routing set --agent claude --tier fast --model YOUR_FAST_CLAUDE_MODEL --effort low
agentlean routing set --agent claude --tier balanced --model YOUR_BALANCED_CLAUDE_MODEL --effort medium
agentlean routing set --agent claude --tier deep --model YOUR_DEEP_CLAUDE_MODEL --effort high
```

You can use the same model in multiple tiers and vary effort only. Omit `--effort`
or choose `native` to omit the effort override and let the client resolve its
default for the selected model. Effort
availability depends on both model and client version. Configuring a preset does
not query your account or prove that a model/effort combination is supported.
The client reports unsupported combinations when launched; AgentLean does not
silently substitute another model or provider.

## Turn it on or off

```sh
agentlean routing on
agentlean routing status
agentlean routing off
```

Configuration lives in `.agentlean/routing.json` in the selected repository. Use
`agentlean routing --target /path/to/repo on` (or `off`, `status`, `set ...`) to
operate on another repository. Status does not create files. Updates are locked,
validated and atomically written. On/off preserves configured presets. Neither
personal Codex nor Claude configuration is edited, and no model IDs are seeded
without your choice. Enabling before configuration is allowed; a missing selected
preset stops launch with an actionable error.

## Preview or launch a task

```sh
agentlean run --agent codex --task "Fix a typo in README"
agentlean run --agent codex --task "Fix a typo in README" --execute
agentlean run --agent claude --task "Refactor concurrent workers" --execute
```

Without `--execute`, the command prints JSON describing the tier, model, effort,
selection reason, working directory and argument vector. It does not start a
client and works without either CLI installed. The preview omits prompt text.
With `--execute`, it starts one installed client by default, sends the task as UTF-8
stdin, streams client output and propagates its exit status. For prompts supplied
through a pipe, use `--task -`. AgentLean stores no prompt or response; native
clients may retain their own session history.

`--target /path/to/repo` chooses the client working directory and routing settings.
The executable is resolved on PATH. On Windows a native executable is required;
batch shims are rejected to avoid implicit shell interpretation. Existing client
authentication, project instructions, permissions and sandbox behavior apply.
No permission-bypass flags are added. Extra repair runs require explicit
`--repair-attempts` with acceptance checks; retries are off by default.
Turning routing off leaves model/effort flags out of the launch entirely.

## Selection rules and overrides

| Signal | Tier |
| --- | --- |
| Short mechanical request with explicit acceptance checks | fast |
| Would-be fast task without checks | balanced |
| Ordinary implementation or uncertain difficulty | balanced |
| Architecture, concurrency, refactoring or debugging signals | deep |
| Higher-risk signals such as security, authentication, migrations or physical safety | deep |

These are conservative keyword heuristics, not semantic understanding or measured
optimal routing. A long trivial task defaults to balanced. A higher-risk mention
in documentation may deliberately send a simple edit to deep. Brief descriptions
can also hide complexity; preview the decision and use explicit hints when needed.

`--complexity simple|standard|complex` overrides the ordinary keyword estimate.
Higher-risk keywords and `--risk high` retain a deep-tier floor. `--failed-attempts N`
escalates one tier per reported failure, capped at deep. This count is supplied
by you after reviewing a failed validation; a nonzero client exit might be an
authentication or network problem, so AgentLean never equates it with insufficient
reasoning or automatically repeats a task.

Fast routing now requires `--checks PATH`, even with a simple-complexity hint.
See [quality gates](quality-gates.md) for baseline/post-run verification and opt-in
bounded escalation. Explicit `--repair-attempts` is the only automatic retry path;
it is triggered by acceptance failure rather than a native client error.

```sh
agentlean run --agent codex --task "Implement parser" --complexity complex
agentlean run --agent claude --task "Fix typo" --failed-attempts 1
agentlean run --agent codex --task "Implement endpoint" --routing off
```

`--routing on|off` overrides the saved toggle for one launch only. Configure a
more capable and appropriately supported preset as deep; AgentLean cannot infer
model quality, cost, speed or remaining allowance from a model ID. The labels do
not enforce a price or intelligence ranking. Savings require real task measurements.
The existing trial recorder separates model and effort when pairing workflow
comparisons; it does not treat different-model runs as equivalent matched pairs.

## Client interfaces

Codex uses `codex exec --model ID -c 'model_reasoning_effort="LEVEL"' -`, according
to the installed CLI help and the official [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Claude Code uses `claude -p --model ID --effort LEVEL` with piped input, as documented
in its [CLI reference](https://code.claude.com/docs/en/cli-reference).
Available effort levels and client behavior can change; verify against the client
you actually run. Client flag generation and process transport are tested locally;
live model requests are not part of the automated test suite.
