# Exact 91e original recovery failure: observation plan

Status: static preparation only. No new native case has run under this plan.

The immutable source is `91e4ae40b5e9b884c54026406299df5000c9c100`.
Original push run 44104161669 / job 134111871255 / artifact 14337038689
reported 1512 tests, one failure, zero errors: the bound old PID was not observed
exiting within the original five-second recovery horizon at
`tests/test_durable_faults.py:1525`. The original raw files, provider identities,
and 266-member source map are preserved in independent evidence commit
`07b0381eef9d6b9a03d0b62b6b7bd1ec1fc81178`; nothing here rewrites that result.
The reference source map and original summary SHA are copied into
`evidence/runs/recovery-horizon91/original_source266.json`.

The cause is **unproven**. A publisher entry freshness assertion may be appended
to its local `errors` list without reaching the failed parent assertion output.
That alone cannot explain the old PID remaining alive: `_supervise` independently
checks expired ownership. Its pipe reads, mutex acquisition, native status call,
kill/join, and replacement startup must also be observed. SQLite's 0.1-second busy
setting does not impose a whole-call wall deadline. `_spawn` does not wait for
READY, and `_record_process` uses the control database rather than the router EX
gate. No mutex deadlock, fixture-only cause, or production bug is presumed.

## Exact proposed single run (requires separate root GO)

Use the new worktree `/workspace/uta-recovery-horizon-91-review`, CPU 2,
`/usr/bin/python3.13`, and only the original
`ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`.
Resolve and record the interpreter before launch. CI ran Python 3.13.18 with
SQLite 3.46.1; this machine currently has Python 3.13.5 with SQLite 3.46.1. A local
result is not an exact CI-runtime reproduction.

The external driver is
`evidence/runs/recovery-horizon91/trace_original91.py`.
Invocation after approval is `/usr/bin/python3.13 DRIVER --run NEW_PRIVATE_OUTPUT`.
The launcher runs a single worker under taskset CPU 2, a new session, and a
27-second watchdog. Whole launch, source checks and own-child cleanup must also
finish within 30 seconds. No retry, other native test, pressure workload, or
other job's SQL/signals is allowed. Before and after, all 266 source members must
match the original map. Production modules and the original test remain unchanged.

The original fixture lease 5, capture horizon 5, recovery horizon 5, API phase
budget 5, and full publication-thread lifecycle budget 15 are unchanged. The
15-second lifecycle includes successful publication; it is not a five-second
end-to-end recovery claim and does not replace any five-second assertion.

The parent-only call-through wrappers observe original calls and return or
rethrow their real results. They record native `WriterFence.status` start,
return or exception and allowed scalar fields, with no additional database
opening or status query. Every event contains monotonic, CLOCK_BOOTTIME and UTC
nanoseconds. A half-second parent sampler records code-only main, monitor and
publisher stacks, monitor alive/stop state, and the two current workers' native
PID/birth/state. It does not acquire the router mutex, call diagnostics, reap
workers, inspect frame locals or serialize financial payloads. Mutex ownership
is explicitly unknown; code frames can show where a thread is waiting.

For the original publisher, the wrapper reads only the named closure cell
`errors`, preserving the original exception type, native error code and bounded
traceback/cause code locations. It does not serialize arbitrary exception messages
or other closure cells. The existing `_expired_gate_observation` is retained,
including failed setup and cleanup evidence. Original publication calls, receipts,
PID births, pidfd exits, and original kill/join/spawn calls are separately logged.
No post-test financial SQL is added: if the original case does not reach its
financial assertions, those facts remain unverified, rather than queried against
a paused or blocked database. Observer overhead may affect scheduling, so even
an exact repeated failure would not by itself establish a unique historical cause.

A successful original case is **NO_REPRO of the historical five-second failure**,
not qualification of source 91e or production. Only the literal historical
assertion is classified as reproducing that assertion; another-stage failure is
reported separately. Watchdog expiry, logger error, sampling unknown, forced
cleanup, residual own children, changed source, or whole time above 30 seconds
must remain visible and make the observation component incomplete/NO_GO. No
failure or unknown may be retried into success. Read-only diagnosis follows;
no runtime or test fix is included in this plan.
