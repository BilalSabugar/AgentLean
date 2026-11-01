# Runtime source

This directory contains the standard-library Python runtime and the portable
instruction assets. `python -m agentlean` calls `cli.main`; the installed
`agentlean` console entry point calls the same function.

Keep provider-specific argument generation in `routing.py`, acceptance execution
in `quality.py`, persistence primitives in `storage.py`, and manual experiment
semantics in `trials.py`. The installer owns only paths recorded in its manifest.

See [architecture](../docs/architecture.md) for module responsibilities and state,
[tests](../tests/README.md) for verification, and [contributing](../CONTRIBUTING.md)
for change requirements. `templates/` is copied to user projects; it is data,
not an instruction to override the user's scope or permissions.
