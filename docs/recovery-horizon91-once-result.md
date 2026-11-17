# Exact 91e recovery investigation: one observed original case

The authorized original testcase passed once on CPU 2, locally, from
14:52:53.241818 to 14:53:01.287274 UTC on 2026-11-17. Whole external duration was
8.045662904 seconds. Classification is **NO_REPRO of the historical CI failure**;
that failure and its cause remain unresolved. Source 91e remains unqualified.
No production runtime or original testcase was changed. No second native run,
additional SQL read, new financial business command, or old-job action was used.

The exact approved observation commit was
`5e26f0acd04b47cdafad942464e70b537c70d30b`, driver SHA-256
`81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee`.
All 266 original source members matched before and after. The local interpreter
was Python 3.13.5 / SQLite 3.46.1; historical CI used Python 3.13.18 / SQLite
3.46.1. No claim of identical CI runtime reproduction is made.

The original raw evidence is copied byte-for-byte into
`evidence/runs/recovery-horizon91/actual-once/`. Its SHA manifest is
`actual-once-sha256.json`. The original CI failure remains separately preserved
in commit `07b0381eef9d6b9a03d0b62b6b7bd1ec1fc81178`.
The read-only `verify_original91_trace.py` generates
`actual-once-derived.json`; it never opens SQL, executes a testcase, or signals a
process. Twenty-seven captured checks are true. The derived report explicitly
keeps one missing positive observer-join observation unknown, so the strict
observation-component gate is **NO_GO/incomplete**, despite the original case
passing. This is not hidden by a process exit code or by retry.

This run captured real retained native READ flock and a successful zero-DML
SQLite availability probe on its first capture. The old bound PID was 230559,
start ticks 6430051, lease generation 1; the supervisor's actual expiry check led
to its original kill call and kernel pidfd exit. Generation 2 was owned by PID
230565. Publication timing, in seconds, was:

| Origin | Milestone | Elapsed |
| --- | --- | ---: |
| Native SH capture | Old PID exit | 4.753877499 |
| Native SH capture | Publication complete | 5.651935522 |
| Original publication thread start | Old PID exit | 0.284567718 |
| Original publication thread start | Original parent EX entered | 0.290452855 |
| Original publication thread start | New native SQL generation observed | 0.857882162 |
| Original publication thread start | Publication complete | 1.182625741 |

The original five-second recovery milestones passed. Publication success fell
within the separate original fifteen-second thread lifecycle, which is not a
replacement five-second end-to-end SLO. Reporting only the subsecond interval
from late publication start would omit most of the stopped-owner lease wait.

Both original publication receipts were actually `SUCCEEDED`:
`market:3:0:db872d742a82ccc8` at sequence 4 and
`market:3:1:db872d742a82ccc8` at sequence 3. The original testcase verified the
unchanged snapshot bytes/digest and each persisted receipt. It reached its
original financial assertions: zero orders, zero accepted events, unchanged
ledger, debt, fills, positions and matches, and unchanged schema/cache versions.
The held command was queued during the held gate; a PENDING acknowledgment does
not mean financial acceptance or settlement.

There were 323 original native status calls, each with a matching return, no
native status exception, and fourteen code-only parent thread samples. Supervisor
alive/stop state, both workers, publisher errors, and three native clocks were
captured. Publisher errors, logger failures, sampling-unknown events, fixture
cleanup errors and forced cleanup were absent. This successful path does not
resolve why the original CI supervisor failed to make progress. It also does
not prove that a publisher-entry race alone caused that failure.

Three spawn starts and returns balanced, covering the two original workers and
one replacement. All three had actual pidfd exit records and were absent at
cleanup. The private new process group/session 230555 was independently scanned
read-only after the run: no PID remained with that PGID or SID, covering possible
unrecorded descendants as well as recorded workers. Output directories were 0700.
Neither the 27-second worker watchdog nor the outer watchdog fired.

The exact driver invokes `watcher.join(1)` and `sampler.join(1)`, but it did not
record their `is_alive()` values after those joins. Their containing worker and
entire native session exited, so no observer thread remains now; that is narrower
than positive recorded proof that both joins completed before worker exit.
This evidence gap is retained in the strict derived gate, not filled by inference
or another native run. Any later recorder revision must separately record those
post-join states and receive its own execution scope. No runtime fix is justified
solely by this non-reproduction.
