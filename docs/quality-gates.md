# Quality-gated efficiency

Fast routing now requires a valid `--checks` manifest. Without checks, a would-be
fast task moves to balanced. Complex and higher-risk tasks retain their deep-tier
floor. Routing off still preserves native model/effort defaults; acceptance checks
can run with routing off, without automatic escalation.

This enforces configured acceptance criteria, not universal output quality. Choose
checks that detect the requested behavior and relevant regressions. A client
exiting successfully, or a command that always returns zero, cannot establish
that a task was completed correctly. Subjective requirements, untested behavior
and physical engineering outputs still need appropriate review.

## Define task-specific checks

Save a file such as `checks.json` in the repository:

```json
{
  "schema_version": 1,
  "checks": [
    {
      "name": "targeted acceptance tests",
      "argv": ["{python}", "-m", "unittest", "discover", "-s", "tests", "-q"],
      "timeout_seconds": 120
    }
  ]
}
```

Use existing project commands. Put cheaper useful checks first, followed by
broader checks when warranted. Names must be unique. `argv` is an argument list,
not a shell string. `{python}` selects AgentLean's interpreter; specify your
project interpreter if it differs. Timeouts default to 120 seconds and may be
set up to 3600 seconds per command.

```sh
agentlean run --agent codex --task "Fix typo in README" --checks checks.json
agentlean run --agent codex --task "Fix typo in README" --checks checks.json --execute
```

Preview validates the manifest without running its commands or starting a model.
Relative `--checks` paths resolve from the invoking shell's working directory;
use an absolute path when launching against a different `--target`.
Only explicitly supplied manifests are loaded. Commands run as your local user
in the selected repository, without a shell; supply trusted commands. Windows
batch shims require an explicit interpreter. Timeout stops the direct process;
commands spawning descendants must manage their own cleanup.

## Execution and success

1. Validate configured model/repair preset definitions before a client call.
2. Run checks as a baseline. A failure, timeout or inability to run stops before
   spending on a model.
3. Launch the selected native client. Nonzero client exits are propagated and
   never interpreted as a reason for stronger-model retries.
4. After a zero client exit, run every check again. Report `checks_passed` only
   when all configured checks pass and the manifest is unchanged.

Checks stop at the first failure. Later checks must run on a passing attempt;
they are not skipped to manufacture success. Logs stream directly to disk rather
than into prompt context or memory. Passing checks are not cached across edits.
The command list is snapshotted before execution and its file digest is checked
for changes. Test sources themselves still need review; AgentLean cannot prove
that an agent has not weakened a test file.

For intentionally failing reproduction tests, explicitly add
`--allow-failing-baseline`. The failing baseline remains recorded and all
post-run checks must pass. Infrastructure errors, timeouts and manifest changes
remain blockers. Without `--checks`, native execution prints an `unverified`
notice; its exit code is not presented as a quality verdict.

## Optional bounded repair

```sh
agentlean run --agent claude --task "Fix parser" --checks checks.json --repair-attempts 1 --execute
```

Repair defaults to zero. You may explicitly allow up to two additional client
runs, subject to distinct stronger presets being available. It requires routing
on and configured checks. Only a post-run acceptance failure permits escalation:
fast to balanced to deep, or balanced to deep. Identical model/effort presets are
skipped; deep never loops at the same preset. The provider, working tree and
original task are retained, with a diagnostic excerpt limited to the last 4000
bytes of the failing check's log. No completed work is reset.

Unchanged diagnostics, client errors, check infrastructure errors, timeouts and
manifest changes stop further attempts. Missing repair presets are detected
before the first client call. Tier labels are user-defined: configure deep as
more capable. AgentLean cannot infer model quality or cost from a model name.
No extra provider calls occur by default.

## Evidence and boundaries

Each checked execution creates `.agentlean/runs/RUN_ID/` with full logs and a
checkpointed JSON report: baseline, manifest SHA256, attempt model/effort, check
outcomes, check/client/total duration and log paths. The original task and model responses are not
stored. Check logs may contain private data. Opt-in repairs forward a bounded
diagnostic excerpt to the same client/provider; avoid emitting secrets in checks.

Exit code 4 means quality gates blocked completion. Native failures preserve
their exit status; configuration/process errors use code 2. A report still
marked `running` is incomplete/interrupted, not verified. Checked executions in
one repository are serialized; external editors and unguarded client runs are
outside that coordination. Evidence is never automatically deleted.

Tests demonstrate avoided blocked and duplicate client calls on fixtures. Real
token, allowance and quality improvements require matched task experiments. No
percentage saving or universal quality guarantee is claimed from these controls.
