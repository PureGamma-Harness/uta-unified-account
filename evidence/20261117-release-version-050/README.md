# Release version declaration and gate checks

Base source: `a407d3c2a639cdf41b55e33eca4765866faec915`, recorded clean at
`/workspace/uta-capacity-next` before creating the isolated
`/workspace/uta-version-050` worktree on `feat/release-version-050`.

This patch declares `0.5.0a1` and removes the archive/installed checkers'
hardcoded `0.4.0a1` expectation. The archive checker reads both declarations
from frozen Git blobs, rejects inconsistent/static-unsupported declarations,
modified tracked files and non-ignored untracked files, and requires one wheel
`METADATA` file with exactly one matching `Version` header. The installed
checker compares distribution and initializer versions with the archive report.

Final focused results, using one CPU (`taskset -c 0`):

| Runtime | Actual suite | Result |
| --- | --- | --- |
| Python 3.10.22 | `test_release_archives.py` | 19 tests, 6.631 s, OK |
| Python 3.12.14 | `test_release_archives.py` | 19 tests, 6.481 s, OK |

The original `0.4.0a1` fixture class and its original assertions remain. A
separate `0.5.0a1` class exercises the same real temporary Git repositories and
ZIP/tar byte checks. Additional controls reject wrong/missing/duplicate headers
(including mixed-case names and misleading body text), two metadata files,
source declaration mismatch, unsupported/dynamic/duplicate source declarations,
executable initializer code and dirty/untracked source. Rejection controls
assert that unrelated runtime/source byte checks still pass where a report is
produced. No project runtime or financial service is invoked by these fixtures.

`original-counterexamples-python310.txt` preserves a run against the exact
archive checker from the base commit: 3 selected tests produced 7 failed
assertions, with no errors. These include acceptance of duplicate identical
`0.4.0a1` headers, rejection of coherent `0.5.0a1` archives and acceptance of a
wrong `0.4.0a1` metadata header for `0.5.0a1` source. It is an expected red
counterexample run, not a qualification result. The preliminary 18-test green
runs are also retained; the final 19-test runs add untracked-source rejection.

`declaration-and-syntax-python310.json` records the working patch's declaration
precheck and exact changed-file hashes. It compiles changed Python sources and
calls the declaration reader without importing `uta`; it does not validate a
frozen project artifact. `evidence-manifest.json` records raw-file digests and
the exact base checker digest. See [commands.txt](commands.txt) for reproduction.
The expected-red unittest output retains four original trailing spaces;
`git diff --check` reports those raw lines. The patch passes that check when
only this byte-preserved raw file is excluded.

No new project wheel/sdist was built or installed. No service, pressure load,
capacity test or full CI was run. All historical artifacts/evidence remain
unchanged. Fresh frozen-source CI/package acceptance is pending integration;
`production_approved` remains false.
