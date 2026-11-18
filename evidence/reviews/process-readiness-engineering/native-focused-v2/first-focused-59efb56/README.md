# First revised pure20: RED, no retry

Frozen target59efb56 / plan2bda673 ran exactly once: **20 methods,
19 methods explicitly OK, one method with three subtest ERROR; zero FAIL,
zero skipped, exit1**. Python3.12.14 used actual affinity[0]. Unittest
reported8.384s and the runner8.519s, within the10s budget. First stdout is
8,678 bytes and stderr is empty, within the combined256KiB cap.

All three errors are `TypeError: unhashable type: 'types.SimpleNamespace'`
at `bindings[process]` in the sticky/inflight guard fixture. They stop before
the relevant postbinding guard assertions. They cannot count as those guards
passing. This is a synthetic fixture adapter error, not an observed native
failure or proof of remediation.

[Intent](intent.json), [complete first stdout](stdout.txt),
[complete first stderr](stderr.txt), [actual exit](exit-status.txt), and
[counts, hashes and postflight](result.json) are retained. All eight runner
input pins matched before/after; all78 materialized inputs and21 preserved
original files remained byte-identical. No original fixture executable,
target module, SQL, native worker/helper, signal or network action ran.

No retry occurred. Original pure7, guard1PASS/5RED, terminal1PASS/7RED and
both PR34 CI FAIL retain their original scope and results. Preflight/native
execution remains unauthorized.
