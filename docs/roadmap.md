# AgentLean roadmap

## 0.1: local foundation

- Portable workflow pack, separate from engineering-specific references.
- Preview-first additive installer for Codex, Claude and generic explicit loading.
- Validated manual trials and conservative matched-pair reports.
- Standard-library runtime and behavior tests.

## 0.2: release hardening

- Atomic trial writes, process-safe locking and strict persisted input validation.
- Managed installs, explicit upgrades/removal and journaled interruption recovery.
- Fault-injection, real process concurrency and isolated installed-wheel checks.
- Package validation, source rebuild checks and cross-platform CI configuration.

## Next: evidence before additional automation

- Validate workflow discovery and behavior in actual Codex and Claude clients.
- Define a small repeatable task suite across coding, documentation and data work.
- Run paired baseline/lean trials on real projects; publish sanitized observations
  including failures before claiming improvements.
- Validate packaging and supported Python/OS combinations in CI.

## 0.3: optional model routing

- Repository-level on/off switch and user-supplied model/effort presets.
- Conservative task tiers with explicit overrides and failure-count escalation.
- Preview-first Codex/Claude launch adapters; native defaults preserved when off.

## 0.4: quality-gated efficiency

- Fast-tier eligibility requires explicit acceptance checks.
- Baseline and post-run verification with checkpointed evidence and on-disk logs.
- Optional bounded escalation driven by validation failures, with duplicate-preset
  and repeated-diagnostic stops. No retries for client or check infrastructure errors.

## Later, when justified by observed failures

- Optional import adapters for documented agent telemetry, keeping provenance and
  distinguishing measured tokens, displayed allowance, cost and estimates.
- Reusable task fixtures, automatic acceptance checks and experiment isolation.
- Evidence-backed reports with uncertainty estimates and quality comparisons.
- Opt-in domain packs and resumable context tooling when they outperform the
  lightweight workflow. Routing remains opt-in; no forced chat resets.

Publishing packages, creating a remote repository, and installing into personal
agent configuration are separate release/installation actions.
