# Six-hour actual-start handoff: collecting finance, live coverage NO_GO

This is a read-only handoff snapshot, not a final result. It was collected in
the separate `feat/managed-long-handoff` worktree based on `ce3045f`. The active
`/workspace/uta-managed-observer` tree, producer source, original control/logs,
timing and processes were not modified. No observer sample, SQL query, restart,
resume, stop or new job was performed by this archive.

The capture window was **2026-11-17 10:27:22.416761–10:27:22.445590 UTC**.
Each JSON file was read through one regular-file descriptor and hashed; these
are several atomic publication points, **not one logical financial SQLite
snapshot**. Different round counts/times may legitimately reflect progress.
`manifest.json` distinguishes original source hashes from redacted export
hashes. Producer error bodies, if present, are exported only as presence/hash.

The original preflight is retained as historical evidence: its
`service_started=false`/`PREFLIGHT_ONLY_NOT_STARTED` describes that earlier check,
not the current job. Actual startup is separately recorded in
`actual-launch.json`, `observer-baseline.json` and `initial-handoff.original.json`:

| Fact | Recorded value |
| --- | --- |
| Producer source | `763202df9cb3ce089721e5281371aff3eab58089` |
| Active supervisor/observer root | `/workspace/uta-managed-observer`, frozen `ce3045f` |
| Supervisor | PID 122905, birth 4679488, detached PPID 1 |
| Original driver | PID 122907, birth 4679495, PPID 122905 |
| Observer monitor | PID 123007, birth 4679847, PPID 122905 |
| Actual observer CLI | PID 123009, birth 4679847, PPID 123007 |
| Actual driver launch | 10:01:08.481980 UTC |
| Original active start | boottime ns `46796458020699` |
| Original deadline | boottime ns `68396458020699` |
| Initial UTC clock mapping | approximately 10:01:09.980709 → 16:01:09.980709 UTC |

The deadline is an original planned time, not actual completion proof. At this
capture the producer reported **running**, active time **1571.792828654 seconds**,
**389 DONE rounds**, 12 worker fault signals and 1 parent fault signal.
`logs_verified=false` is expected before final export/audit. These are original
producer reports, not a new independent financial audit. Latest observer finance
was inflight/unproven and deliberately not compared. The final financial gate
therefore remains **PENDING, not passed**.

Live coverage was already permanently **NO_GO**: 26 observed samples, 8 technical
read unknowns and maximum consecutive technical unknowns 3. Both the total budget
3 and maximum consecutive budget 1 had been exceeded. Those causes remain
unknown unless separately established; later successful reads cannot erase the
NO_GO. The agreed policy keeps collecting financial data to the original
six-hour target, rather than stopping or resuming for a coverage failure.

The effective preregistered gates remain:

- 21600 actual active seconds, 5400 rounds at .25 rounds/s; one original driver
  and no continuous-target resume. Default worker/parent schedules remain 30/300.
- Supported CLI observation interval **61 seconds**, from amendment `992e4d6`;
  original plan `92fd79f` remains unchanged. Twelve original-boottime 1800-second
  blocks each require a real stable compared/passed golden. A final snapshot
  after 21600 seconds does not backfill the last block.
- All read errors and inflight/unknown records remain. Health facts, empty
  alerts or process survival do not imply a finance pass. Confirmed financial/
  ledger failures request official drain only for the matched new driver.
- Final financial evidence still requires actual golden, integrity/FK checks,
  exact original command effects, verified logs, same-watermark reopening and
  actual private complete-clone producer cold audit with the strict long receipt.
- Replay means independent journal hash, per-currency conservation, complete
  owner/asset posting reconstruction and business joins. Full `uta_events`
  business reexecution and every-decision risk reexecution remain **null/unmeasured**.

The separate 250k-history **NO_GO** is retained verbatim; this three-account
low-rate job does not qualify general large-history recovery. Production and
10k claims remain false. There is no early six-hour or live-coverage approval.

Only birth-matched new-job `/proc` metadata was inspected. All four identities
were alive and pinned to CPU 0 at capture. Each producer and actual observer
stdout/stderr pipe matched an O_RDONLY supervisor descriptor; 5 supervisor
threads were observed, including 4 waiting in `anon_pipe_read`. This supports
current bounded pipe draining, not future operation or a cumulative byte count.
No stream target was opened or read, so the supervisor's data was not consumed.
`queued_pipe_bytes=null`; this proc view does not expose the child-list node,
recorded as unavailable rather than an empty list. Registered PPID relationships
provide the observed lineage. PIDs 4471/8784 were not inspected or signalled.

This archive is an explicit JSON/proc allowlist. No `private/`, authentication
database, TLS key, raw stderr, nonce-bearing clone, command line or environment
was archived. `capture-readonly.py` records the collector; it is not a runtime
observer or an eligibility check. The frozen active tree stays untouched.
