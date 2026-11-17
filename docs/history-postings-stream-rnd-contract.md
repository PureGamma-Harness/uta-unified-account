# Full-history postings stream: R&D contract, not capacity acceptance

Author branch `perf/history-guard-investigation`, base `c30457227e2bfc0a1e665ff67c9c148855ac624a`. No runtime implementation, new SQL, profile, service, load or fault experiment has run at this contract milestone. The author cannot independently accept their own eventual change.

## Evidence and attribution boundaries

The [reproducible inspection](../evidence/runs/history-perf-rnd/inspect_existing.py) imports no UTA code and reads only enumerated public source, JSON and exported profile text. Its [output](../evidence/runs/history-perf-rnd/existing-evidence.json) binds every input by bytes/SHA256. No binary pstats/pickle is loaded.

Two 250k failures have different boundaries:

* The older `d08ab26` runtime / `91c7b0a` 250k tool recorded generation one acquire, full replay begin, no renewal or replay end, and lease expiry while that child was alive. Generation two later replayed in 4.718s. This establishes one expiry/replacement, not a permanent crashloop. The historical result stays NO_GO.
* The later `763202d` / `d886cdb` attempt spent 58.268230s including metadata and stopped before durable enqueue or worker acquisition. It retained the expected 250k head and an enabled-fence marker after native preflight, but no complete initial/final independent reference or setup phase timings. It cannot establish an owned replay expiry or attribute the elapsed time to a particular schema refactor. Its original watchdog and NO_GO remain intact.

The valid independent worker text profiles from `7a06c05` show substantial repeated work. Worker 18157 ran 760 account supervisions (5.838574s cumulative), 3130 data-guard inventories (1.791906s cumulative), 2226 control-schema checks (.661278s cumulative), and 81 audit records (.033741s cumulative). Worker 18158 similarly ran 611 / 2751 / 1988 / 90. Those cumulative times include child calls and waits and cannot be added into CPU percentages. The parent dispatcher profile has documented mixed-thread anomalies; its status timing is excluded from reliable phase attribution. Old WAL/group-writer profiles suggest SQL/commit and transaction density, but belong to different runtimes and scopes.

Current static inventory:

| Path | Work and growth variable | Decision |
| --- | --- | --- |
| `DurableLedger.verify` | All N events, all P postings, hashes, exact balances; N separate indexed `postings WHERE sequence=?` SELECTs. Current primary key `(sequence, ordinal)` already supports the order. | Investigate one ordered postings cursor; no cache/index/schema migration. |
| `WriterFence.status` through `Database.read_transaction` | Connection setup plus full control/data schema inventory at transaction begin/end, then live lease/clock; O(schema objects), not O(journal history). The process supervisor polls every .05s, subject to work and waits. | Preserve every guard/clock/PID/boot/identity check. No safe measured shortcut proposed. |
| `BatchStore.unresolved/_verify_history` | All B immutable manifests, members and outcomes; B outcome lookups and member lookups. | Required recovery proof; do not replace by unresolved-only query without a new integrity protocol. |
| `BatchStore.prepare` | Unresolved-manifest anti-join; all pending rows for eligibility, twice when preparation proceeds. | Pending queue growth differs from total journal growth; do not infer the 250k ledger failure from it. |
| `BatchStore.record_failure` | All matching failure-event payloads until original attempt/phase/generation is found. | Rare error-path candidate, no supporting timing; defer. |
| `DecisionAudit` constructor/replay | All installed source files plus loaded financial code/runtime artifact. Replay recomputes current artifact. | O(source bytes), not O(history). Preserve immutable-source/loaded-code checks; no cross-PID artifact cache. |

`managed_credit` confirms its current work is default-off correctness development, not a performance profile. This branch changes none of its credit, policy, authority or archive modules.

## Proposed local implementation

Only add an explicit exact-bool, default-false `ordered_postings` option to `DurableLedger.verify`. No caller or production configuration enables it. The default branch remains the original per-event query. The experimental branch opens one `SELECT sequence,ordinal,account,asset,units FROM ledger_postings ORDER BY sequence,ordinal` in the same existing transaction and groups consecutive rows per original event. It retains event ordering, every posting, full integrity/FK/schema/trigger checks, normalization, canonical integer bounds, fingerprint/hash checks, cumulative signed-balance bounds, exact final materialized balances and the same error category/text for valid-schema malformed histories. No prior successful replay substitutes for the current one.

This changes SQL statement dispatch, not the O(N+P) financial proof. Group memory must be bounded by one event's postings plus one lookahead row (the old implementation also materializes one event's postings); do not build a whole-history postings list. A missing group still reaches the existing minimum-two-postings error. Orphans remain rejected by the unchanged first foreign-key check. Physical insertion order is irrelevant: explicit SQL ordering restores `(sequence,ordinal)`. Any unexpected unmatched/remaining inventory must fail closed, never silently disappear. An unsupported/tampered catalogue must not be made eligible by a cache.

Automatic startup, final cold replay, code/schema/config fingerprints, clocks, leases, PID ownership, transaction lifetime, persistence and return count stay unchanged. Rollback is to leave the option false or remove this isolated opt-in; no data migration or authority rollback is needed. A performance improvement remains unmeasured until the authorized component, and is not assumed.

## Manual oracle and malformed cases before measurement

The [case inventory](../evidence/runs/history-perf-rnd/posting-stream-cases.json) is synthetic and is a contract, not an executed test result. With USD scale 2, event one transfers 1250 units from `a` to `b`; event two transfers 300 units from `b` to `c`. Manual totals are `a=-1250, b=950, c=300`, zero total liability/asset change, N=2/P=4. Physical reverse insertion is still the same journal. Expected error text/order comes from the pinned default verifier, with a separately developed literal integer/hash reference required for valid data. The future differential must exercise missing/extra/orphan groups, sequence/ordinal gaps, canonical order, hash links, units and both signs of cumulative overflow; multi-fault cases must compare the first error as well as failure versus success.

## Single proposed scratch component, NOT_RUN

Root must approve the exact frozen harness/source before execution and coordinate CPU4 release with `managed_credit`. One own temporary, private, unmanaged synthetic SQLite authority, one process, CPU4, total wall watchdog 15s including fixture/setup, differential, profile, final cold verification and cleanup; no production DB, service, worker, registered benchmark variant or existing job. If the cap is reached, preserve partial phases and NO_GO; do not extend or silently rerun.

Use N=512 valid events, P=1024, public `DurableLedger.post` in two real 256-event transactions. Preserve first observed/cold-like and repeated/warm-like timings separately; neither proves physical cold disk I/O or throughput. Within one bounded execution alternate old/new old/new (and report order), record wall/CPU per call, exact N/P/returned counts, SQL trace counts and SQL text classes, source and harness hashes, logical selected row/UTF-8 bytes, `/proc/self/io` read counters and caveats. SQL trace counts are statements, not SQLite internal index steps. `read_bytes=0` can simply mean the kernel page cache satisfied reads; do not label it absence of work.

Include only predeclared small malformed authorities, each new/private with deliberate test-only mutation and exact inventory proof; no guard is disabled in either verifier. A corrupt fixture may temporarily remove/restore original triggers only in its offline construction, before either path runs. Then reopen and use the original default path for final full cold replay, independent literal reference and balance/head comparison. Mutation/reference/cleanup cost belongs to the total component budget. If these controls cannot fit 15s, defer the profile instead of reducing correctness coverage or widening the budget.

Acceptance is component-only: all complete row counts and literal reference match; both branches return equal count or exact same documented exception; no mutation/guard bypass; original default remains disabled/unchanged; new option invalid types reject before opening storage. Another group must review and decide whether to integrate. No 10k/s, sustained duration, order/fill throughput, 5s recovery RTO, HA or production statement follows.
