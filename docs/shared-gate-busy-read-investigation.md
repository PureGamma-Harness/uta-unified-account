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

Successful captures followed by an unexpected unknown native read still fail.
No production supervision, lease, timeout, schema guard or financial formula
is changed. The original .1-second reader budget is not enlarged.

## Proposed real BUSY microcomponent, not yet authorized to execute

Create a new synthetic temporary managed database and one explicitly owned
scratch child with a real native writer token. That child uses a separate real
SQLite `locking_mode=EXCLUSIVE`/BEGIN transaction to hold a schema-observation
lock; no financial DML is required. Record its pidfd/birth, inject only its
SIGSTOP, and demonstrate the original native `WriterFence.status` genuinely
returns BUSY through `_load(sqlite_master)`.

Apply the new non-financial undo helper to that exact child, release the real
lock on its resumed control path, and take one native fresh same-owner/generation
read before allowing any further capture. Check no token/expiry/data mutation,
no unobserved-as-active value, and no masked primary error in cleanup. This
intentional EXCLUSIVE scratch lock is a compatible BUSY mechanism, not proof
that the historical worker's exact WAL operation was the same.

The proposed microcomponent must use an external <=30-second whole watchdog,
own-group pidfd cleanup and new private output. All forced cleanup, logger
errors, unknown results or residual children are NO-GO. No old job SQL/signals,
pressure workload or second original-case attempt is authorized by this plan.
Only static edits and archival have occurred; `production_approved=false`.
