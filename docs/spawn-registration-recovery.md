# Spawn registration failure recovery: scoped candidate, wider acceptance pending

This change repairs an exception path in the managed process supervisor. It is
not a production approval or a claim that the original CI publication timeout
has been uniquely reproduced or explained.

## Evidence and source boundary

The starting point is `e4396b4b1fd9c2e3a138e48a045feffe158705cc`.
Its runtime and tests are byte-identical to the frozen source909 authority;
that running authority is neither changed nor used by these tests.

PR22 first CI run `44162304965`, job `134319073058`, Python 3.11.18 /
SQLite 3.46.1, finished 1,801 tests with zero assertion failures and one error.
`test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers`
timed out acquiring the first publication EX gate with the original 4s budget.
The original artifact also contains an uncaught supervisor-thread
`sqlite3.OperationalError: locking protocol` from `_spawn` -> `_record_process`
-> connection initialization `PRAGMA journal_mode = WAL`. The original text has
no clock/PID anchor proving which happened first or whether they share a cause.
The original artifact ZIP is 92,276 bytes, SHA256
`9ea4bae56cd6c2697cd613972bbcbf56c0fc3bffbd3c720313fc740ca66eaffc`;
private originals remain in the separately reviewed first-CI archive.

The existing stopped-owner test confirms that some SH holder exists before it
stops its selected worker. It does not bind that observation to that worker's
current PID birth and kernel lock. That is an evidence gap, not proof the test
is wrong. Polling EX acquisition may also encounter SH contention; this patch
does not alter flock policy or claim it caused this CI failure.

## Runtime behavior

The child remains behind its start gate until its SPAWNED registration returns
success. On a registration-phase exception the parent stops and reaps only its
own new, unreaped child and closes its owned resources. A registry COMMIT can
have succeeded before the exception: its original row and nonce remain intact,
its outcome is reported as UNKNOWN, and its INSERT is never replayed.

Every unclosed handle and unconfirmed child remains reachable in pending
cleanup state. Neither `_spawn` nor `start` can bypass that state; `close`
retains the supervisor flock while cleanup is unknown. A later cleanup attempt
may resolve it. Cleanup completion is not assumed from an exception or timeout.

Only known SQLite BUSY, LOCKED or PROTOCOL registration failures with confirmed
cleanup permit a new child/new nonce. Retry intervals rise from 50ms to 1s.
Attempts are unlimited at this bounded rate; there is no finite-attempt budget.
Other failures block this shard. The monitor rechecks shutdown after obtaining
its mutex and before retrying. Unrelated unexpected monitor errors are not
silently converted to readiness.
Resolving a previously unknown cleanup does not clear a terminal registration
error; that object remains blocked even after all resources have been closed.

Diagnostics expose a fixed typed failure record and `supervisor_alive` through
the router and managed gateway adapter. They contain no raw exception message,
SQL, path or nonce. A dead supervisor cannot be financially ready. `recovered`
means that a later child's registration returned success; normal lease,
generation, market and worker-ready checks still determine readiness.

No schema migration is required. Lease TTL, SQLite busy timeout, publication
timeout, financial WAL/FULL COMMIT, token guard, schema verification and audit
verification are unchanged. Spawn/registry/cleanup still execute under the
existing global mutex and may delay other shard supervision for the existing
database timeout. This is an explicit remaining limitation, not a fixed or
proven cause of the original timeout.

## Model evidence already collected

`PYTHONPATH=. python -B tests/test_spawn_registration_recovery.py` defaults to pure
model cases. Its wrapper rejects real SQLite connections, real process starts
and `os.kill`. The first fixed run passed 8/8 in 0.027s. The same test bytes
against a fresh source-e439 runtime archive failed six assertions and raised
one error in 0.035s. The latter error follows the original uncaught monitor
registration path. This is model regression evidence, not a native CI rerun.
The shutdown/retry model passes on the old implementation because its newly
introduced retry path is absent there.
The initial fixed 8-case text did not capture its own imported runtime path;
the later prepare-only hash check is a separate process and does not supply
that missing observation. Preserve this limit when citing the initial result.

The cases cover gated-child cleanup, modeled post-append lost reply, unknown
cleanup across close/start, failed handle-close reference retention, unknown
private errors, monitor recovery, shutdown retry exclusion and typed HTTP
diagnostics. Raw first outputs, the original runtime identity and static
prepare result are retained under
`evidence/recovery/spawn-registration-20261117/`.

## Exact bounded native diagnostic and first authorized result

`tests/stopped_gate_recovery_probe.py` is prepare-only by default. It checks all
runtime blobs against `ff814d4bcaee079b0e0503ea8072c24e3563c443`, and byte-pins
the unchanged source-e439 `owned_run`, orphan-reaper and kernel-lock helpers.
It reports its own and the new test module's SHA256. The static preparation
performed no SQLite connection, worker start or signal operation.

The root-authorized once-only combined command was:

```sh
python -B tests/stopped_gate_recovery_probe.py --execute --case all \
  --cpu 1 --output /workspace/uta-spawn-native-once-private-20261117
```

Execution creates only a new private directory and fresh synthetic authorities.
The original ownership harness starts a new CPU-1 session with an unreaped
leader, pidfd and affinity ACK. Inner alarm is 15s, owned-run wall budget 20s,
TERM/KILL grace 1s each, orphan reaping at most 5s: planned overall budget 30s.
This userspace budget cannot guarantee kernel uninterruptible I/O completes.
Bounded stdout/stderr are preserved, at most 512KiB total. The harness refuses
signals to pre-existing protected PIDs 4471, 8784, 310035, 310039, 310266 and
310269, or any group containing them. Only new owned children/session members
can be stopped, terminated, killed and reaped. No existing authority is opened.

Three one-shard fault cases verify failure before INSERT, an actual registry
COMMIT followed by injected reply loss, and monitor recovery after an actual
COMMIT plus injected reply loss. These use real SQLite and real child gates.
The injected OperationalError is not a claim of inducing SQLite's native
locking-protocol fault. The second case must retain its original SPAWNED row,
leave lease generation zero and confirm the gated child exited. The third
must retain all three SPAWNED rows, reacquire generation two and reach actual
READY with a distinct PID within the unchanged 4s check.

One two-shard kernel case uses the unchanged source test setup, lease 0.6s and
publish timeout 4s. It pins the selected current child by pidfd, birth, boot and
UID; requires an active lease and that exact child's kernel SH record for the
expected router-lock inode; stops it through its pidfd; and rechecks retained
SH before publishing. Capture is at most 1s. An absent or raced capture is
UNKNOWN, not a reason to rerun or stop a different child. Partial failures leave
the first raw evidence intact for review.

Parent-only `sys.settrace` / thread tracing records bounded function phases,
clock, shard/PID, lease numeric facts, EX attempts and exception type/native
SQLite code. It never prints SQL parameters or nonce. Tracing and polling
change scheduling: every output is labeled instrumented diagnostic, not the
original CI reproduction, capacity result, SLA or production approval. The
first failure, timeout or unknown is preserved and escalated; no repeat-until-
green or widening of publication/lease timeouts is authorized.

An additional delayed-cleanup/terminal-error regression passed with all nine
model cases in 0.024s on fixed runtime `ff814d4`. A first direct file invocation
omitted `PYTHONPATH=.` and failed at import with `ModuleNotFoundError`; that
original harness error is preserved alongside the corrected command's output.
It did not run a model case, SQL, worker or signal operation.
`python -B tests/spawn_registration_model_probe.py` subsequently passed 9/9 in
0.026s with source proof and imported runtime path captured in the same process
and the same output stream, before its blocked-I/O model tests. Its first raw
output is `pure/terminal-fixed-same-process-first.txt`.

The single approved native batch subsequently passed 4/4 in 4.091s. Its
detached outer supervisor completed in 5.302555280s and both ownership harness
leaders were reaped. The 440-event trace is complete. The kernel case retained
the exact target SH through STOP, then completed publication in 1.126711011s
with publishing=false, halted=true. No repeat was performed. The detached
wrapper itself was exited/Z under PID1 at the metadata-only post-check; the
observer could not reap it. Full first raw evidence and these scope boundaries
are in evidence/recovery/spawn-registration-20261117/native-once/README.md.
Broader regression QA and independent acceptance are still pending; original
CI causality is not proven.

## Candidate rollout and rollback

Broader native regression acceptance and independent review are still required. Keep existing
authorities on their pinned binaries. Deploy this candidate only to a new
synthetic authority after model tests, the bounded native batch, existing
process/gateway regressions and independent review pass. Check worker PID /
generation, supervisor liveness, retained registration rows and readiness.

For rollback, stop new command admission and query all accepted command IDs;
do not replay unknown commands. Confirm every candidate child has exited and
all pending cleanup is resolved before releasing supervision or starting the
old binary. Retain registry and financial audit rows. If cleanup or financial
results remain unknown, keep the authority halted and use ownership/replay
reconciliation; never delete the database, erase a SPAWNED row or relax a
writer fence to force startup. The change has no schema rollback step.
