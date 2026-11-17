# 8b native lease-read lock error: test-fault recovery plan

Base: `8b7f544fcbdfd540d43de1d6560022c6ebbd3799`, immutable freeze.
The original Python3.13/SQLite3.46 run executed1472 tests with **1FAIL and
1ERROR**, clean unchanged source. The historical generator failure is handled
separately. The new error is a real `sqlite3.OperationalError: database is locked`
at line1367 while observing the selected paused worker's native lease. Its
`finally` repeated the same read at line1501 and masked the first exception.

The complete original summary, worker result and raw log are preserved. All263
before/after input hashes were compared to actual frozen bytes and Git blobs.
The earlier exact3af single-component PASS stays unchanged and scoped; it was
never a complete-release PASS. Local3.10/3.12 had only the separate history
failure; the new3.13 error must not be collapsed into a uniform single failure.
No conclusion about the current remote CI matrix is made from these local logs.

Subsequent original PR artifacts are preserved separately under `remote/`.
Python3.11 has the paused native lease BUSY and repeated cleanup BUSY. Python3.13
instead fails first at probe BEGIN IMMEDIATE with `locking protocol`, then the
same message masks it during cleanup. Both actual PR merge reports retain
`5cdc9b5abbd6ad86fb031512890d7b685219f8a6`; their263 input maps equal8b but
their Git SHA is not rewritten to8b. Both remain1472/1FAIL/1ERROR, not uniform
BUSY. The original traces do not print the native numeric error attribute.

## Narrow test-only change

An unsuccessful capture must undo only the fault injection it issued. It must
not try to establish financial authority by reading a database while its own
paused process may retain a SQLite writer/schema lock. Record `lease_observed`
as false rather than inventing active status. A pidfd, birth/boot/UID and exact
selected child still constrain SIGCONT. This removes the test's own SIGSTOP;
it grants no trade, renews no lease, changes no token or data, and does not
signal a replacement or foreign process.

After undo, require the selected bound process to have actually resumed and
left its native SH scope. Then perform one fresh native lease read using the
unchanged .1-second observation timeout. Only the same owner/generation with
active=true permits another capture. A repeated BUSY/unknown read fails rather
than polling until green. Known inactive/changed ownership fails and cannot be
laundered into a resume/retry. Original capture limits remain eight attempts
within five seconds; all original later recovery and publication assertions
remain in force.

Cleanup makes no native lease read. It uses the exact owned pidfd/birth and its
own injection state. A known inactive binding is not resumed; any forced own
child cleanup is explicitly recorded and makes a component NO-GO. If cleanup
itself fails, append safe details to observations while preserving any primary
test exception. An otherwise successful body cannot hide a cleanup error.

The concrete candidate records the unavailable/skipped resume observation as
`observed=false` before `undo_owned_test_stop`. That helper accepts only this
pidfd's still-matching PID/birth/boot/UID. It has no SQL or renewal call and its
record explicitly grants no financial authority. A known invalid owner,
generation or inactive state cannot use the normal resume path. The case then
waits only for genuine kernel progress (no longer stopped and no bound SH),
performs one fresh .1-second native read, and requires the original owner and
generation active before another attempt. Failure of that single read is not
retried. The original eight-attempt/five-second capture budget is unchanged.

Successful captures followed by an unexpected unknown native read still fail.
No production supervision, lease, timeout, schema guard or financial formula
is changed. The original .1-second reader budget is not enlarged.

## Explicit own-stop protocol policy follow-up

The newly observed protocol message warrants a separate test-only UNKNOWN
policy. `router_writer_available_without_dml` keeps its strict BUSY-only default.
Only an explicit boolean `own_injected_stop=True`, supplied by this case after
its bound pidfd stop and retained native SH proof, permits native SQLITE_PROTOCOL
base15 or Python3.10's exact builtin no-native-code `locking protocol` form to
return `available=false`, `lease_observed=false`, technical UNKNOWN. It is never
a healthy lease, database or financial result. The same undo/progress/one-fresh
proof protocol must succeed before another capture within the same8/5 budget.

Native IOERR, CORRUPT, NOTADB, LOCKED and other errors still raise; they permit
cleanup of an injected fault, never continuing capture. Present invalid native
attributes cannot use a string fallback. No production error classification is
changed. Pure synthetic exception-vector definitions cover this dispatch and
are labelled as such, not as an actual reproduction of native protocol15.

## Proposed real BUSY microcomponent, not yet authorized to execute

Create a new synthetic temporary managed database and one explicitly owned
scratch child with a real native writer token. That child uses a separate real
SQLite `locking_mode=EXCLUSIVE`/BEGIN transaction to hold a schema-observation
lock; no financial DML is required. Record its pidfd/birth, inject only its
SIGSTOP, and demonstrate the original native `WriterFence.status` genuinely
returns BUSY through `_load(sqlite_master)`.

Use an importable scratch-child target with two explicit barriers. First the
child acquires its own five-second native token and actual private router SH;
the parent takes a genuine fresh owner/gen/expiry observation. On the second
barrier the child acquires its SQLite EXCLUSIVE transaction and reports the
real lock operation complete. Only then does the parent stop that exact own
pidfd and call the real .1-second `WriterFence.status`, requiring actual BUSY.

Apply the new non-financial undo helper to that exact child, allow the child to
ROLLBACK/close its existing SQLite transaction and release its own SH, and take
one native fresh same-owner/generation read. The child stays alive on a final
barrier so process exit cannot stand in for a genuine active lease. Do not
renew/reacquire its token. Compare the expiry and financial rows to the first
fresh observation; then let the child release its own authority and exit
normally. The parent must preserve the actual BUSY exception if cleanup is
entered under that primary exception; the helper performs zero lease reads.
No unobserved-as-active value is accepted. This intentional EXCLUSIVE scratch
lock is a compatible BUSY mechanism, not proof that the historical worker's
exact WAL operation was the same.

The proposed microcomponent must use an external <=30-second whole watchdog,
own-group pidfd cleanup and new private output. All forced cleanup, logger
errors, unknown results or residual children are NO-GO. No old job SQL/signals,
pressure workload or second original-case attempt is authorized by this plan.
Only static edits and archival have occurred; `production_approved=false`.

The explicit driver is `controlled_lease_busy.py` in this evidence directory.
It has no default action; `--run NEW_OUTPUT` launches one CPU2 scratch component
using the selected Python executable, with a27-second child-group watchdog and
<=30-second whole budget. Parent status calls are actual call-throughs counted
by phase; undo must add zero native reads and retain the original real BUSY
exception object. A final barrier keeps the native owner alive until the fresh
positive proof. A real BUSY5 is required; protocol15 is not manufactured. The
code has only been compiled, not executed. Further authorization must select
the exact commit/helper hash and runtime before that one native component.
