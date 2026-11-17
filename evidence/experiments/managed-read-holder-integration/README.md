# Minimal producer holder lifecycle candidate

This branch follows the actual isolated prototype f92a2d6. The implementation
moves that helper to `benchmarks/managed_read_holders.py` and its owned-temp
tests to the matching test module. Historical prototype reports still describe
the exact earlier f92 source and are not relabeled as final-source evidence.

The producer constructor initializes `read_holders=None` before initialization
and includes helper bytes in its existing frozen-source manifest. `run()` opens
the three holders after its original initial state writes and before server
startup / the original active-start clock. It supplies original job metadata
file identities, rejecting a mismatch before the first affected SQLite open.
The class still checks current identity after real open/warm, existing private
direct mains, WAL format, query-only and idle autocommit. Standalone owned-temp
tests can omit an original manifest; the producer always supplies it.

The original loop, duration/rate/planned rounds, clocks, fault schedule,
recovery, financial verification and PASS expressions are unchanged. Idle
holders survive planned child generations and remain through native drain,
final verification, event/log export and final progress publication. `close()`
closes them after child drain and before releasing run.lock, including cleanup
when drain raises. Partial opens close in the helper; initialization failure
does not open holders or replace its original error. No global Database
connection policy, writer token or observer write privilege changes.

Actual incremental micro run: 2026-11-17T11:49:59.131741Z to 11:50:00.680359Z,
shared 1.548630986 seconds. Exactly ten selected cases per runtime (five actual
SQLite/kernel-RO prototype cases plus five lifecycle cases) ran on CPU 2 under
Python 3.10.22 / 3.12.14 / 3.13.5, ResourceWarning fatal and AS 512 MiB cap.
Each has zero failures/errors/skips/expected failures/unexpected successes;
suite times are 0.393078 / 0.426463 / 0.441036 seconds. The runner imposed a
shared 29-second child budget below the authorized 30-second ceiling. Source
hashes before/after match; exact selected names, argv, versions, affinity and
raw output are retained.

Lifecycle fixtures use real temporary checkpoint SQLite transactions, original
event-chain export/audit, the real status/progress writer and real holders.
They deliberately stub server start/drain and leave a stopped ACTIVE round so
no business replay or financial service constructor executes. These are unit
lifecycle checks, not transport/service readiness or financial PASS. They
prove holders exist before the original start clock, remain through actual
progress publication, then actual connections are closed. They also cover a
real original-metadata mismatch after one successful partial open, startup
failure, pre-initialization failure, and holder closure despite drain error.
Existing native kernel-RO read, actual writer truncate, explicit real cursor
close, real query-only denial, partial-open and owner-thread cleanup cases were
repeated against the moved helper.

This does not guarantee sidecars under arbitrary external unlink, I/O failure,
crash or every final-close filesystem state. Complete parent-path authorization
remains with original native private-path/authority controls, not this metadata
sampler. Source-side idle connections do not establish a stable logical point,
financial readiness, full business/risk reexecution or the cause of the old
ten uninstrumented read errors. Existing final same-watermark golden/FK/reopen,
source qualification and original duration gates remain mandatory. Budget
accounting still includes surviving WAL/SHM; no performance or RSS claim is
made from these microtests.

No original source/job, paused diagnostic clone, service or new long job was
opened or started by this micro run. This candidate requires independent root
review, new combined-source full three-runtime/CI/package qualification and
a separately authorized actual service smoke before any new six-hour GO.
The original stopped attempt remains NO_GO for six-hour, financial-final and
coverage, regardless of this candidate's micro results.
