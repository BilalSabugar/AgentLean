# Measurement protocol

## Experiment design

1. Define an observable task outcome and frozen acceptance checks before running.
2. Prepare equivalent isolated workspaces from the same revision and starting
   state. A commit hash alone is insufficient if dirty files or external state differ.
3. Fix toolchain, dependencies, fixtures and available tools. Give that environment
   an ID. Give the acceptance criteria an ID; keep their definitions with the task.
4. Hold agent, exact model and reasoning effort constant when testing the workflow.
   Record `none` for effort if the client has no such setting. Record the workflow
   version in notes. Do not change model or tool permissions between paired runs.
5. Run baseline and lean with the same `pair` ID. Use fresh task workspaces,
   equivalent context and no access to the other run's solution. Alternate ordering
   between pairs to reduce learning, cache and timing effects.
6. Record all outcomes, elapsed minutes, corrective iterations, manual corrections,
   evidence locations or check descriptions, and material caveats. Use a fresh pair
   ID for repeated runs; do not discard failures to improve the reported ratios.

The CLI enforces valid values and matching labels. It cannot establish that the
operator's labels, check results or observations are true. Keep full evidence on
disk. No checks, agent executions, allowance queries or telemetry collection happen
automatically. `observed_at` is recording time in UTC, not an inferred run start.

## Allowance observations

Record remaining allowance only when displayed by the provider. Scope identifies
product, plan and window type, such as `codex/my-plan/weekly`. Compare matched runs
within that scope; the tool never normalizes across products. Exclude allowance
observations spanning resets, replenishment, unrelated account activity or plan
changes. Keep the run's duration and outcome, omit usage, and explain in notes.
The current CLI accepts one allowance window per run, not multiple windows.

Consumption is `before - after` in percentage points. Increases are rejected.
Zero deltas are retained as observations but excluded from allowance reduction
ratios for either arm, because rounded UI readings can obscure consumption.

## Report interpretation

Groups separate agent, model, effort and allowance scope. A pair additionally
requires identical task, revision, environment, acceptance criteria and pair ID.
Mismatches are reported as unmatched runs rather than silently paired.

All outcomes, elapsed time and manual corrections appear in variant totals.
For runs with observed allowance, the variant summary also reports verified
completions per percentage point consumed, including failed and blocked runs in
the consumption denominator. Missing observations are excluded and their coverage
is visible in `observed_allowance_runs`. A zero denominator yields no ratio.
Paired outcome transitions include failures and blocked runs. Reduction ratios
use only pairs where both runs passed: `(baseline - lean) / baseline * 100`.
A positive reduction favors lean; regressions remain negative. Time ratios require
positive baseline duration; usage ratios require positive consumption in both arms.
Ratios are conditional on successful completion: examine the outcome counts first.

Each ratio includes its count, median and observed min/max. Small samples and
hand-chosen tasks do not support general savings claims. Run several realistic
tasks with repetitions; preserve raw data and disclose missing evidence, display
rounding and other confounders. Token and cost accounting, automated grading and
statistical uncertainty estimation are future work.

## Log integrity and recovery

The JSONL log includes schema version, UUID and recording timestamp. Existing
records are retained when a new record is added, with the complete log written
to a temporary file, flushed, and atomically replaced while holding a writer lock.
Invalid or truncated records stop reads and subsequent appends with a line number.
Duplicate JSON keys, nonstandard numeric constants, empty persisted identities,
duplicate IDs and duplicate variants in a matched pair are rejected. An OS-backed
advisory lock on a persistent sidecar `.lock` file coordinates AgentLean writers,
waiting up to ten seconds for contention. OS locks release on process exit;
the existence of a sidecar file does not mean a writer is active.
External editors do not honor it; do not edit a log while recording. Reads do not
acquire a write lock and see a complete snapshot. Use local filesystems; network
filesystem behavior and hostile concurrent external edits are not supported.

Use `agentlean check --file PATH` to validate a log. If an external edit or an older
version left a corrupt record, first ensure no writer remains, back up the log,
and inspect the reported line against your evidence. Repair it explicitly; the
tool never drops records or repairs evidence automatically. Do not remove lock
files while a writer is active. `report --output PATH` atomically exports JSON and
rejects destinations that alias the source log. Avoid sharing private account
details or logs. Large logs require memory and whole-file rewrites; this is a local
experiment tool, not a telemetry service.
