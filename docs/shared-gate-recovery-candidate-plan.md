# SPAWNED registration candidate: next pure run

This is a prepared plan, not permission to execute. The one old-source baseline
is sealed in commit `e96f5af` and must not be repeated or replaced. The current
candidate has not been executed.

Runtime base is `6010e920a168b35fccfc9ef9ee34e030b28b11d9`. Only
`uta/durable_process.py` changes: import `copy`; for SPAWNED only, make a shallow
copy of `control.control`, reduce its `timeout` with `min(original.timeout, .1)`,
and run the original transaction and original single INSERT on that copy. Its
SHA256 is `f2093101f7b7cf5eaa5604639a3892bcb0fd37f7421e171e242f6157416019ca`.
The source patch changes no other method AST and no SQL.

The control DB is a `Database`. Its current instance fields are path, timeout,
writer token, lease clock and boot ID. Existing `Database.for_writer` already
uses shallow copy to retain subclasses and fields. The copy retains existing
file identity validation, connection setup, role selection, initialization write
gate, transaction guard, COMMIT/rollback and close hooks. Changing only the copy's
timeout never changes the shared control DB's configuration. Event kinds OWNED,
COORDINATOR and ORPHAN_KILLED still use the original object and timeout.

The registration failure contract remains unchanged: append outcome UNKNOWN,
child gate closed, cleanup of that exact new child, no uncertain INSERT/nonce
retry, and a new child only after recognized transient error and confirmed
cleanup. Unconfirmed exit/close or a terminal registration error blocks new
children. Lease observations still authorize no kill on UNKNOWN or mismatched
ownership. This is a conditional monitor progress repair, not proof of PR 35's
unique cause or actual native recovery.

`tests/shared_gate_registration_candidate_model.py` requires exact candidate
source bytes, exact unchanged old driver bytes and exact first baseline stdout
bytes before extracting the actual methods. It compares all extracted method
AST hashes except the intentionally changed `_record_process` against that
baseline. It reuses the fixed sixteen finite scenario inputs against candidate
methods without rerunning the baseline, then adds eight direct record checks:
four event kinds times timeout 10/.025. Those direct checks require preserved
subclass/hooks/shared state and path/token/clock/boot fields, unchanged original
timeout, no increase of the smaller timeout, one transaction and one append.

Proposed focused budget: one candidate invocation, CPU 1, ten real seconds at
most, 24 finite scenarios (below 128), four finite virtual monitor turns per
recovery scenario, zero unittest discovery. The driver's internal real-time
deadline is nine seconds. Hard-fail guards reject actual SQLite connect,
BaseProcess.start, os.kill, pidfd_send_signal, Thread.start and real sleep.
Only fake DB/Process/Pipe/clock objects execute actual extracted methods.

The run must use a new first-candidate artifact directory, preserving stdout,
stderr, exit status, script/source hashes and actual-method AST digests. No retry
or sample skip is allowed. Any failure is the first candidate failure. A result
of MODELED_BOUNDARY_PASS means only these pure assumptions and methods pass.

The fake conflict advances virtual time by its connection timeout. This is an
explicit conditional latency assumption. SQLITE_LOCKED/SQLITE_PROTOCOL can have
different native behavior; internal WAL protocol retry/backoff and OS blocking
can exceed the busy handler budget, even with timeout zero. No .1-second function
bound, five-second native recovery guarantee, actual kill/reap/kernel SH
release, higher-generation lease, READY, market ACK or financial reconciliation
is established by this model. Original CI FAIL remains FAIL and its cause
remains UNKNOWN. Native execution requires separate authorization.
