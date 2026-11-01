# Contributing to AgentLean

Contributions that make agent work easier to verify and less wasteful are welcome.
Start with a reproducible bug, a focused documentation fix, a meaningful test or a
sanitized experiment. Read [the code of conduct](CODE_OF_CONDUCT.md).

## Before changing behavior

Search existing issues and the [roadmap](docs/roadmap.md) once the repository is
published. Discuss substantial provider integrations, dependencies, schema changes
or permission-related behavior before implementing a large change. Small fixes
can go straight to a pull request. See [governance](GOVERNANCE.md) for decisions.

Do not post private account details or project logs. Potential vulnerabilities
belong in [the private security channel](SECURITY.md), not a public reproduction.

## Set up development

Use Python 3.11+ and a local virtual environment; see
[installation](docs/installation.md) for Windows and POSIX executable paths.

```sh
python -m venv .venv
# Activate it for your shell, or use its Python executable directly:
python -m pip install -e ".[dev]"
```

The runtime and tests use the standard library. The development extra supplies
lint, coverage, build and metadata-checking tools. No real model credentials or
provider calls are needed to run the suite. Test client behavior with fixtures
and explicit process boundaries rather than spending on live model requests.

## Make a focused change

In a Git checkout, create a topic branch from the current main branch. Preserve
unrelated changes and use existing code patterns. Add a behavioral regression
test for a real failure mode; avoid tests that merely repeat implementation text.

Keep these contracts intact:

- User-edited or unowned instructions are never silently overwritten or removed.
- Failed storage operations preserve existing evidence; concurrent writers cooperate.
- Existing schema-1 trial logs remain readable unless a migration is explicitly designed.
- Routing is opt-in and does not weaken native client permissions.
- A successful client exit does not override failed acceptance checks.
- Logs and synthetic fixtures do not become claimed performance benchmarks.

Update the user guide and changelog for visible behavior changes. Runtime changes
belong in `agentlean/`, tests in `tests/`, documentation in `docs/`, and practical
starting points in `examples/`. See [architecture](docs/architecture.md).

## Validate

```sh
python -m unittest discover -s tests -v
python scripts/check_docs.py
python -m ruff check .
python -m ruff format --check agentlean tests scripts
python -m coverage run --branch -m unittest discover -s tests -v
python -m coverage report --fail-under=85
```

Run focused tests while iterating, then the relevant full checks. The suite uses
real local processes for locking, transport and crash recovery, with simulated
clients for model work. Windows junctions cover path confinement when symlink
creation is unavailable. CI is configured for Linux, Windows and macOS/Python
combinations; passing local checks does not establish a successful remote run.

For packaging and clean-source checks, follow [releasing](docs/releasing.md) and
[the scripts guide](scripts/README.md). These checks do not publish anything.

## Open a pull request

Describe the concrete problem and resulting behavior, the actual validation and
any compatibility risk. Link the issue when relevant. Use the PR template and
include only evidence a reviewer needs. Do not claim tests you did not run.

Efficiency claims need repeated matched tasks, identical acceptance criteria,
quality outcomes and the relevant environment/model/effort metadata. Include
failed and blocked runs. See [measurement](docs/measurement.md); synthetic smoke
tests demonstrate behavior, not real-world credit savings.

By contributing, you offer your contribution under the [MIT License](LICENSE).
Retain necessary third-party attribution and do not submit material you cannot
license. There is no additional CLA or mandatory sign-off configured.
