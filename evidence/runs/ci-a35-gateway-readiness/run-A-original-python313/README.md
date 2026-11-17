# RUN-A: original two cases, one authorized local execution

Result: **NOT_REPRODUCED**, 2/2 passed in 2.735 seconds, no retry loop of the
test run. Local Python 3.13.5/SQLite 3.46.1 is not the CI Python 3.13.18 build.
The actual source commit was `3772aa8`, a35 plus original evidence/docs only.
The runner was untracked during this run; its exact bytes are bound in the
manifest. All measured runtime/fixture/test inputs remained unchanged.

Diagnostics is call-through traced, with no result/lease/market modification
by the tracing wrapper. Five actual observations completed in about 24–38 ms.
Both native owners were generation 1, lease-active and owner-ready. The original
test's shifted parent clock produced genuine market_future and market_stale
rejections with ready=false; the unshifted samples were ready. No local
unknown-owner/control-timeout or expired-lease sample occurred in this run.
This cannot identify the phase or cause of the old uninstrumented CI failure.

The original CI raw failure and permanent NO_GO remain in the sibling original
artifact directory. No original CI job was rerun or relabelled as green.
