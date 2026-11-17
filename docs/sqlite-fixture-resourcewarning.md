# SQLite fixture resource ownership

The successful CI job `133823402337` still emitted an unclosed SQLite connection warning at line 887 of `evidence/runs/durable-final-preflight/ci-pr-success-133823402337.txt`. The original full log SHA-256 is `9e45c12f4ef170e3073f47a2cc1e42f19cda2d8bcad9aed8d6d2e60f4a47e0d0`. The literal warning and adjacent successful results are retained in [the excerpt](../evidence/runs/sqlite-fixture-resourcewarning/ci-warning-excerpt.txt); the existing full CI log is not rewritten.

The warning appeared while `test_parallel_misses_and_evictions_remain_bounded` allocated threading objects. The reserve kernel case does not open SQLite. Without an allocation traceback, the original CI log cannot uniquely identify that specific connection or prove the kernel case allocated it. Garbage collection can expose an earlier fixture's unclosed connection.

A focused Python 3.13.5 / SQLite 3.46.1 probe at baseline `5aa8c67` ran seven existing signing/fencing cases with allocation tracing and explicit collection after each case. All seven tests succeeded, yet produced **11** unclosed-database ResourceWarnings. Allocation stacks identified the raw SQLite contexts in `test_request_signing.py` (1 connection), `test_writer_fence.py` (6), and `test_writer_fence_legacy.py` (4). Python's connection context manager commits or rolls back; it does not close the connection.

The fix wraps those connections in `contextlib.closing` and retains their original connection transaction contexts. Assertions, guard rejection, backup semantics, lease rules and production `uta/` files are unchanged. The identical seven cases and forced-GC probe then succeeded with zero captured ResourceWarnings. No collection assertion was removed or warning filter suppressed.

| Evidence | Result |
| --- | --- |
| [Before repair](../evidence/runs/sqlite-fixture-resourcewarning/red-py313.txt) | 7 successful tests, 11 ResourceWarnings with allocation stacks |
| [After repair](../evidence/runs/sqlite-fixture-resourcewarning/green-py313.txt) | 7 successful tests, 0 captured ResourceWarnings |
| [Related modules](../evidence/runs/sqlite-fixture-resourcewarning/focused-suite-py313.txt) | 54 tests passed in 10.788 seconds; raw output has no ResourceWarning |

The [manifest](../evidence/runs/sqlite-fixture-resourcewarning/manifest.json) records raw artifact digests and before/after test source hashes. The [exact probe source](../evidence/runs/sqlite-fixture-resourcewarning/allocation-probe.py) retains its original worktree path; set `ROOT` to the desired checkout when reproducing elsewhere. Run it with Python 3.13, passing `--expect-warnings` on the pre-fix source and omitting that flag after repair. It checks warning counts separately from unittest success and forces collection after every case.

The broader focused command was:

```sh
/usr/bin/python3.13 -X tracemalloc=8 -W always::ResourceWarning -m unittest \
  tests.test_request_signing tests.test_writer_fence \
  tests.test_writer_fence_legacy tests.test_reserve_kernel -v
```

These local results do not retroactively make the successful CI job warning-free. A successful unittest summary or validation `passed` flag alone does not establish zero ResourceWarnings; even warnings promoted to errors in a destructor may be reported as unraisable exceptions instead of ordinary test failures. This is focused fixture validation, not a new full CI result, stability run, financial change or production approval.
