# Releasing AgentLean

1. Set `agentlean.__version__` and update the changelog. Package metadata reads
   that value directly. Preserve schema compatibility or document migration.
2. Run the contributor checks and inspect the full CI matrix. Windows, Linux and
   macOS plus Python 3.11 through 3.14 are included; local checks alone do not
   establish those combinations.
   Run `python scripts/check_docs.py` and prepare an allowlisted source ZIP with
   `python scripts/prepare_source.py --output release-source/agentlean-source.zip`.
3. Build into a clean output directory (`python -m build --outdir release-dist`).
   Run `python -m twine check --strict release-dist/*.whl release-dist/*.tar.gz`.
   Check only distribution archives, excluding generated checksums. Inspect both archive contents for
   accidental logs, credentials, local dependencies or old build output.
4. Run `scripts/release_check.py` against that exact wheel. Also build a wheel
   from the source distribution and run the same check against it. All smoke-test
   observations are synthetic and confined to temporary directories.
5. Record artifact SHA256 digests and test evidence. The CI package job uploads
   candidate archives and checksums for inspection. It does not publish packages.
6. Before a public release, establish repository/package ownership and verify the
   contact in [MAINTAINERS.md](../MAINTAINERS.md) and the private reporting path.
   Publishing credentials belong in the release service, never in this checkout.
7. Publish only the inspected artifacts through an authorized release action.

The repository intentionally has no automatic registry publication or deployment
workflow. Configured CI is not evidence of a successful remote run. Real task
benchmarks and live agent-client validation are separate acceptance gates for
claims about agent behavior or efficiency.
See [the launch checklist](open-source-launch.md) for repository setup. The owner
will publish; no remote or registry URL is fabricated in the source metadata.
