# First full-matrix supervisor: independent static review

This review covers the external QA controller at commit
`9a001dfee2ce88d37346a367837150a22d1a74c0`, not a completed full QA run.
Its `tools/run_spawn_recovery_full3.py` SHA-256 is
`355095946cb735094c6806c5d8aa3ddcfdcff6c180aece727e895df6b6be9b71`.
The frozen financial/test source remains `6b7d473c0fbf92b17c146140c88eb2c25d38dce1`;
the production runtime implementation remains the `ff814d4` revision.
No test, SQL connection, native fault, signal or QA process was executed by
this review. A prepared pure-model tool operation was interrupted before
creating its script or executing it; this is not model evidence.

The earlier detached-launch metadata failure was addressed with a pipe GO
after successful identity persistence and parent stream closure. Typed
integer counters reject JSON booleans, and finalization attempts direct-child
reaping and pidfd closure after a group-signal failure. Those improvements do
not resolve the following four boundaries. The candidate is blocked pending
their exact revision and a limited follow-up review.

1. **Implicit orphan cleanup can disappear from acceptance.** The reused
   `_orphan_reaper` kills newly adopted live children at context exit. It does
   not populate its yielded `adopted` list. The controller checks only the QA
   leader's original process group. An escaped-session child could therefore
   require forced cleanup while the controller still reports PASS. The
   controller must observe and preserve this condition as UNKNOWN without
   changing the frozen test helper.
2. **Whole-matrix completion precedes its final durable record.** The 2,730s
   decision is computed before the final summary write/fsync. A delayed final
   write can cross the declared budget while retaining a true completion
   field. The final persistence boundary and subsequent acceptance must be
   explicit. The documented 900s limit is an active-runtime budget; this
   review does not redefine it as the entire post-processing budget.
3. **Executable hashes do not bind the loaded runtime.** The controller
   inherits `PYTHONHOME`, `LD_LIBRARY_PATH` and `LD_PRELOAD`, and it does not
   compare the actual summary's Python/SQLite identity to approved values.
   These environment controls must be rejected or removed and actual runtime
   identity checked. A label such as `python313-sqlite346` is not evidence.
4. **A GO delivery can be unknown before the local flag changes.** The
   launcher sets `released=True` after `os.write`. If the byte is delivered
   and an asynchronous exception occurs before that assignment, the handler
   can kill the supervisor as if QA were not authorized. A QA child may
   already occupy its own session. The write attempt must enter an explicit
   possibly-delivered state; a lost reply cannot be treated as confirmed
   pre-GO cleanup. This is a static failure-path finding, not a reproduced
   kernel write or process failure.

The author acknowledged these four items and is preparing a revision. The
fixed CPU 4, sequential Python 3.10 / 3.12 / 3.13 order, 900s active budgets,
2,730s whole budget and original four-second test assertion remain unchanged.
No full-matrix execution is authorized by this review. The first PR22 CI
failure remains a failure with unproven cause; the four-case native component
and its wrapper-zombie boundary retain their narrower original conclusions.
