# Tests

The suite uses unittest and the Python standard library. Run from the repository
root:

```sh
python -m unittest discover -s tests -v
```

| Area | Coverage |
| --- | --- |
| Core CLI and trials | Input validation, persisted identity, pairing, failures and report boundaries |
| Reliability | Concurrent writers, process-exit locks, atomic replacement, rollback and crash recovery |
| Routing | Default-off behavior, tier selection, provider arguments, concurrent settings updates and stdin transport |
| Quality gates | Baseline/post-run checks, gated success, timeouts, manifest changes and bounded repairs |
| Public source preparation | Private-file exclusion, link validation and guarded source export |

No live model calls or credentials are needed. Native clients are mocked or
replaced with small local subprocess fixtures. Synthetic timings and results are
test data, not efficiency evidence. Keep new fixtures deterministic and sanitized.

For a focused run, use unittest discovery's `-p` filter, for example:

```sh
python -m unittest discover -s tests -p test_quality.py -v
```

Full contributor checks, including lint, coverage and isolated-wheel checks, are
in [CONTRIBUTING.md](../CONTRIBUTING.md). This suite is intended for trusted local
filesystems; it does not establish network-filesystem semantics or live provider
behavior. Actual platform results are in [release validation](../docs/release-validation.md).
