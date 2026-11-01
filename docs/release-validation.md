# Local release validation: 0.4.0

Recorded on 2026-11-01. These are software verification results, not agent
efficiency benchmarks.

| Check | Result |
| --- | --- |
| Windows / Python 3.11.17 | 61 tests passed; no skips |
| Windows / Python 3.14.7 | 61 tests passed; no skips |
| Coverage on Python 3.14 | 92% combined statement/branch coverage |
| Ruff lint and formatting | Passed |
| Public documentation | 100 local links and 2 check examples validated; external links not fetched by the local checker |
| Clean source export | Allowlisted source and per-file SHA256 inventory; private local inputs excluded |
| CI YAML parse | Passed; remote matrix has not run |
| Wheel and source metadata | Twine strict checks passed |
| Archive contents | Templates present; original ZIP, local dependencies, private handoff and trial logs excluded |
| Isolated installed wheel | Install preview/apply/repeat, trial/check/report, routing presets/toggles/previews and uninstall passed on Python 3.11 and 3.14 |
| Wheel rebuilt from source archive | Build and isolated lifecycle check passed |

Reliability tests cover eight concurrent writers, OS-lock release after process
termination, a real installer process exiting mid-write followed by recovery,
failed replacement preserving prior log bytes, rollback after a manifest-write
failure, user-edit preservation and Windows junction path confinement.
Routing tests cover both providers' flags, default-off behavior, native-setting
preservation, missing/invalid presets, six concurrent preset updates, complexity
and risk rules, explicit execution, and real subprocess UTF-8 stdin transport.
Native client interfaces were checked against installed Codex help and official
Codex/Claude documentation. No live provider requests were made.

Quality-gate fixtures verify that failed baselines spend no client call, bad output
cannot hide behind a zero native exit, post-run checks gate success, and optional
repairs preserve completed work. Duplicate presets, repeated diagnostics, native
errors, timeouts and changed manifests do not cause unbounded retries. These
are synthetic behavioral tests, not measurements of provider-token savings.

The open-source package candidates and SHA256SUMS are in
`release-dist/open-source-0.4.0/`; earlier runtime artifacts are preserved in
`release-dist/0.4.0/`. A separate allowlisted source ZIP is in `release-source/`. Release
smoke-test observations are synthetic and removed with their temporary directory.
No personal agent configuration or global Python PATH/registry settings were
changed. Local development dependencies and a Python 3.11 interpreter were placed
in ignored workspace directories for validation.

Remaining acceptance gates: remote Linux/macOS/Python-matrix execution, live
Codex/Claude invocation, real matched task experiments, and maintainer/registry
setup before public publishing. No registry publication or deployment occurred.
