# Frequently asked questions

## Does AgentLean make a model smarter or increase subscription limits?

No. It changes workflow and optionally selects your configured model/effort for
new native-client runs. Model capabilities and provider accounting stay with the
provider. No real-world efficiency gain has been established yet.

## Is it only for engineering?

No. The core is domain-independent repository work. The initial idea came from
an engineering workflow pack, but physical CAD, PCB, robotics and embedded outputs
still require their own specialist validation.

## Can it change the model in this already-open chat?

No. Routing applies to new Codex/Claude CLI runs started through AgentLean.
It does not edit your personal settings or control an active desktop conversation.

## Why is a simple task using balanced instead of fast?

Fast requires an explicit acceptance-check manifest. Without it, a would-be fast
task moves to balanced. Mixed/uncertain tasks can also route to balanced, while
higher-risk signals keep a deep floor. Preview the reason before executing.

## Does a passing test prove the output is good?

It proves only that the configured command returned success. Acceptance tests
must cover the task and relevant regressions; subjective requirements and test
integrity need review. The quality controller does not independently prove those.

## Does AgentLean use an LLM to decide the model?

No. The current policy uses local conservative rules and explicit user hints.
There is no extra classification request. Tier labels do not establish an actual
quality or price ordering; configure them appropriately and measure the results.

## Is my data uploaded automatically?

Previews, storage and manual reports are local. `run --execute` sends your task to
the installed client using its native authentication and behavior. Explicit
repairs also send a bounded diagnostic excerpt. Check output and native session
history may contain private data; see [security](../SECURITY.md).

## Which platforms and clients have been verified?

Local checks passed on Windows/Python 3.11 and 3.14. A broader CI matrix is
configured; it has not run remotely. Command generation and process transport are
tested, but live model/client behavior remains unverified. See
[the validation report](release-validation.md) for evidence and limits.

## Where is the public repository or registry package?

The public remote URL and registry publication are not configured in this
checkout. The source and release preparation tools are provided without invented
links or package-availability claims. Follow the
[open-source launch checklist](open-source-launch.md) before publishing.
