# Readiness fixture timing repair and retained failures

This is a test-only repair based on
`d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6`. Production readiness predicates,
financial APIs, one/two-second quote TTLs, writer leases and diagnostic timeout
limits are unchanged. Complete new full3/CI8/package qualification is still
required; original d421 and bb34 failures remain NO_GO.

## Original evidence

Evidence-only commits584a1e7 and9366246 preserve both original ZIPs and all
three members from push44085180665/Python3.11/job134045628549 and
PR44085188612/Python3.13/job134045656182. Their252 source-input hashes match
exact d421 before and after the original runs. The original PR merge SHA
`7114617951b6b4e4313c19439f853fdd115e35d0` is retained. Both ran1413 tests:
the push had0 failures/1 error; the PR had2 failures/0 errors; neither skipped.
The archive originally assumed ZIP member order; the PR orders its members
differently, so the follow-up checks the exact member set while preserving
original ZIP bytes and order. No historical result was rewritten.

The push failed when activating an original one-second quote after completing
an intentionally partial publication. The PR observed a real mixed
`market_stale`/`diagnostic_timeout` report and later saw false on one immediate
post-clock-rollback observation. These records establish the failed assertions,
not a uniquely proven historical scheduling cause.

## Test changes

In the partial-publication test, a real parent READY frame is awaited before
an actual native PID/birth/generation/lease witness. No repeated SQL diagnostic
probe occupies the startup gate while the child is still initializing. The
unchanged one-second observation budget remains bounded; no READY means a
failed precondition, never an inactive-owner inference or permission to trade.
The initial quote is created only after that actual owner witness, while the
other shard remains deliberately held by the original external test fence.

The original SID1 must then finish with both original CIDs SUCCEEDED, and both
persisted payloads must equal its unchanged bytes. A distinct current SID2
provides the healthy activation precondition. The test waits until that SID2
actually expires and requires stale rejection; distinct SID3 demonstrates
recovery. It never edits an old SID's time or accepts SID2 as evidence of a
completed SID1. Explicit snapshots passed into process activation remain
unchanged; default snapshots are created after the worker start call.

The process tests reuse the existing strict readiness-sampling functions via
a module import, avoiding duplicate discovery of another TestCase. Stale and
future observations may finitely await only explained typed observation
transients, for at most one second. Every incomplete observation remains
literal false for both ready fields; known inactive native ownership fails
immediately. The fixed EarlierClock covers the entire bounded future
observation. Both original payloads are checked before and after that clock
scope, then a distinct new current SID demonstrates recovery instead of
assuming the original quote is still fresh after elapsed wall time.

## Actual controlled results

All runs used CPU2, real newly created temporary authorities and spawned
owners. No existing job SQL, service, pressure test, benchmark or full suite
was started. The control driver was committed before its first execution;
controls delayed real work or held only owned fixture gates. No report,
exception, lease or snapshot was fabricated.

| Record | Actual result | Interpretation |
|---|---|---|
| `original-red` |6 tests,3 FAIL,0 ERROR,12.685s | Mixed stale/timeout and restored-clock contention were reproduced. Sampling failed earlier with SID1 still publishing; the intended post-completion expiry control was NOT_REPRODUCED in that run. Three original negative controls passed. |
| `fixed-green` (historical intended phase name) |5 tests,1 FAIL,0 ERROR,11.809s | Both process cases and persistent UNKNOWN/real inactive-owner controls passed. Sampling's initial diagnostic-heavy native startup precondition did not obtain a READY owner in one second; it remained RED. |
| `sampling-native-frame` |1 test PASS,3.464s | The revised READY-frame-first native witness completed and the intended original-SID expiry control was exercised. Only this case was rerun, as authorized. |

The sampling closure records actual PID196640/birth5802445/generation1 before
SID1 creation. SID1 first returned shard0 SUCCEEDED/shard1 PENDING and the
partial observation remained false. Both original receipts later SUCCEEDED;
the real completed-SID1 return was deliberately delayed beyond its original
one-second quote TTL. SID2 became healthy, actually expired to two stale
rejections, and SID3 recovered. Complete stdout/stderr are retained; closure
stderr was empty. Total recorded component time across all three runs is
27.958s, below the authorized60 seconds.

The first run captured only a native-child Process/Traceback prefix, so its
complete error source remains **UNKNOWN**. That gap and the earlier sampling
failure are retained explicitly. No later green replaces either. No watchdog
fired in the successful sampling closure. The previously passing process and
negative-control functions are AST-identical to those in their actual passing
record; all final cases were not rerun together. This narrow evidence does
not replace exact-source full-candidate validation.

## Reproduction, delivery and rollback

Original CI and component files, source hashes, function-identity checks and
the driver are under `evidence/reviews/readiness-d421-fixture/`. The driver
requires a new output-stage directory and keeps all failed records. The final
sampling-only stage has an owned observation watchdog and does not rerun the
other already recorded controls. The two modules add no test methods or
imported TestCase classes; the next full gate must verify its discovery count.

All591 runtime/source assets under uta/tools/benchmarks/formal/scripts/config/
deploy and packaging configuration compare byte-for-byte with d421. There is
no database, compatibility or financial-rule migration. Rollback reverts the
two test files in a new commit and retains evidence; it neither restores an
older writer into capability-marked storage nor modifies original authorities,
clocks, commands or balances. Integration must freeze a new source and complete
fresh full local, remote CI and package gates before any new smoke/long run.
Production and real-funds activation remain blocked.
