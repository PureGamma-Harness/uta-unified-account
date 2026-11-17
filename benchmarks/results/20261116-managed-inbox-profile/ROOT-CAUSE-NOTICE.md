# Historical probe is not stability-green

The original `7a06c05` probe and `99d461a` archive remain byte-for-byte intact: 200 durable inbox ACKs,171 financial successes,18 product refusals,11 router-halt refusals, and one observed SQLITE_IOERR_SHORT_READ522. The final RO ledger/order/audit checks do not establish that the concurrent lock protocol remained valid throughout the run. This old result is **NO-GO for stability, capacity and production acceptance**.

SQLite first-party guide§2.2 states that closing a descriptor for a database file can cancel all process-owned POSIX advisory locks on that inode, including locks held by other SQLite connections/threads. SQLite3.51+ WAL defenses are not a cure-all. Original application preflight opens/fstats/closes the published database inode, so this is an application-level unsafe pattern, not a reason to relax integrity checks or simply downgrade SQLite.

The independent lock suite reproduced that kernel protection is lost while the original SQLite transaction still reports active; corrected storage candidates preserve it across Python3.10/3.12 with SQLite3.53.1 and Python3.13 with SQLite3.46.1. Original red results, the incomplete first repair and the later bounded green results are retained in the copied report. Their run durations are correctness-test timings, not throughput evidence.

The unsafe mechanism is confirmed. Attribution of the single historical522 event remains a candidate, because that probe did not capture the affected shard, FD/syscall or WAL identity. No precise event-level causality or absence of hidden effects is inferred from matching symptoms. Repair throughput and stability remain unmeasured here.

First-party source: https://sqlite.org/howtocorrupt.html#posix_close_bug . Full original HTML bytes, normalized section excerpt, immutable source digests and copied independent/implementation reports are under `posix-close-review/`. `manifest-before-posix-review.json` preserves the prior manifest; every file it originally named remains unchanged. No new load or changes to the running24h producer/observer were made.
