# Development and release scripts

Run these from the repository root with Python 3.11+. They do not publish files
to a remote service or send provider requests.

| Script | What it does | Dependencies |
| --- | --- | --- |
| `check_docs.py` | Checks public documentation links, JSON example definitions and obvious private-data markers | Standard library |
| `prepare_source.py` | Builds an allowlisted public-source ZIP without local development data | Standard library |
| `check_artifacts.py` | Inspects wheel/sdist contents, writes checksums and optionally rebuilds the sdist | Standard library; installed build backend for rebuild |
| `release_check.py` | Installs one wheel into a fresh environment and checks its lifecycle | Standard library and bundled pip |

```sh
python scripts/check_docs.py
python scripts/prepare_source.py --output release-source/agentlean-source.zip
```

The source exporter refuses to overwrite an existing output. Use a new filename
for a new snapshot. It excludes local dependencies, caches, logs, evidence,
private handoffs and the historical input archive. It is an additional packaging
check, not a comprehensive secret scanner or a substitute for reviewing the
staged Git diff.

Package checks, after installing the development extra:

```sh
python -m build --outdir release-dist/current
python -m twine check --strict release-dist/current/*.whl release-dist/current/*.tar.gz
python scripts/check_artifacts.py release-dist/current --rebuild source-wheel/current
python scripts/release_check.py release-dist/current
python scripts/release_check.py source-wheel/current
```

Use a clean candidate directory containing exactly one wheel and one source
archive. Release smoke tests use synthetic observations in temporary directories.
Their PATH excludes native model clients so a broken test guard cannot reach a
real provider. For the full procedure see [releasing](../docs/releasing.md).
