# Task brief

## Outcome

Fix the parser so a quoted comma remains part of a field and an unquoted comma
separates fields. Preserve the existing public function signature.

## Done when

- Existing parser tests still pass.
- A quoted-comma regression test fails before the change and passes afterward.
- Empty fields and escaped quotes retain their documented behavior.
- The final report names the actual checks and any untested boundary.

## Scope

Change the parser and its focused tests. Preserve unrelated work, avoid dependency
upgrades and use the existing project conventions. Do not weaken tests to obtain
a passing result. Attach the relevant acceptance manifest when using a checked run.

This is an illustrative task. Replace it with your real inputs and acceptance
criteria rather than treating this example as a benchmark.
