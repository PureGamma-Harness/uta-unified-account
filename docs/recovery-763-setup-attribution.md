# 763 setup attribution and proposed next measurements

The authorized250k case remains **NO-GO** under its original56/58/60s workload/cleanup and62s metadata policy. It exhausted the budget before a durable command or supervised worker ownership. The1k contract passed; neither result establishes a250k owner-start or crash-recovery RTO. The [preserved evidence](../benchmarks/results/20261117-recovery-763-authorized/README.md) is committed separately from the actual immutable driver `d886cdbfafbc491e1a7705313080f910712bd185` and runtime `763202df9cb3ce089721e5281371aff3eab58089`.

This analysis reads source and retained JSON only. It opens no SQLite authority, performs no new replay/profile/cohort, changes no budget/TTL/financial rule, and does not revise the failed outcome. The quiet execution window already ended.

## What the retained metadata establishes

The large case has250000 journal events at the expected head, an existing empty inbox, only the generation-zero `enabled_guard_v1` event, no worker trace/acquire/renew/READY, no copied-driver summary and no completed final independent replay proof. The original leader was interrupted and killed under the registered watchdog; cleanup left no owned process.

In the unchanged normal source order, persisted `enabled_guard_v1` is after native offline journal preflight. It therefore establishes that this full native preflight returned before the fence was enabled. It does **not** establish that the entire `initialize()` returned, that the first independent reference check completed, or where SIGINT arrived. No per-phase wall/CPU timestamps for those stages survived. The absent `credit_schema` is expected before the worker prepares its credit module; it is not a newly discovered schema fault.

Only the end-to-end measured outcome can be reported:58.265583s workload/cleanup,58.268230s including metadata, stopped without a durable CID or owner. An expected head and native preflight are not replacements for the missing independent before/after reference proof.

## Complete-history work in the source path

The following references pin the actual runtime763 and actual driver d886. The external driver contains an older `uta/` tree alongside it; that tree was **not** the selected runtime and is not used for this attribution.

| Stage | Source path and scan | Evidence boundary in this case |
|---|---|---|
| Construct fresh authority | `initialize()` constructs `ShardRouter` before invoking bootstrap ([runtime:555](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/durable_process.py#L555)); each service constructor verifies its journal ([sharding:181](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/sharding.py#L181), [service:175](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/service.py#L175)). | At this point the fixture has **zero** journal events. This is not a repeated250k replay. |
| Generate fixture | Public `DurableLedger.post(..., connection=...)` calls,250000 events in977 batches of at most256 ([driver:242](/workspace/uta-recovery-retest-plan/benchmarks/run_recovery_scaling_60s.py:242)). | Each post validates/normalizes, performs indexed ID/head/balance reads, saves postings/hash/seal and joins its real batch transaction. It does not invoke full-history `verify`. |
| Offline validation and sealing | After bootstrap, all-shard `_preflight_managed_ledger_sources` calls the full native verifier ([runtime:574](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/durable_process.py#L574), [runtime:320](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/durable_process.py#L320)), then queue/fence/config sealing follows. | One completeN-event native replay is on this path before the persisted enabled marker. Tail control/configuration return timing is unknown. |
| Initial independent check | After `initialize` returns, `check_history` performs integrity/FK checks, every event/posting, two SHA256 recomputations per event and exact balance comparison, before enqueue ([driver:260](/workspace/uta-recovery-retest-plan/benchmarks/run_recovery_scaling_60s.py:260), [checker:161](/workspace/uta-recovery-retest-plan/benchmarks/run_recovery_scaling_60s.py:161)). | AnotherN-event traversal is specified. Its begin/end was not durably recorded; completion is unknown. |
| Worker ownership/start | Only after enqueue does `start()` spawn a child; acquire precedes `_OwnedStartup` and one complete owned read-only replay ([runtime:450](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/durable_process.py#L450), [startup:291](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/startup.py#L291)). | **Not reached** here. There is no evidence of a worker lease expiry or a completed owned-start attempt. |
| Close/final reference | If `router` was assigned, finally invokes a further complete independent `check_history`; `summary.json` is written only afterward ([driver:308](/workspace/uta-recovery-retest-plan/benchmarks/run_recovery_scaling_60s.py:308)). | If SIGINT arrived during the initial check, finally could start another full traversal and be killed before summary write. This is a source-supported hypothesis, not an observed signal location. |

Thus full-history traversals repeat across the **whole experiment** for different validation purposes. The source does not establish multiple service constructors replaying the same250k journal during this fresh initialization. The expected worker replay is additional work in a stage the large case did not reach.

Native `DurableLedger.verify` includes SQLite integrity/FK checks, fetches all event rows, selects postings per event, recomputes canonical units/fingerprints/hash links and balances ([storage:474](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/storage.py#L474)). The independent checker performs its own integer/composition/hash proof. These scans must remain intact unless a separately reviewed protocol preserves their complete guarantees; the current task proposes no removal or bypass.

## Static comparison rules out one proposed explanation

The [machine-readable AST comparisons](../benchmarks/results/20261117-recovery-763-authorized/static-attribution.json) compare763 against both `d08ab26` and `91c7b0a`. All14 comparisons match after normalizing only the compared root function name: ledger `post`/`_normalize`, database `_using`, old `_role_transaction` versus new `_role_transaction_body`, writer joinability, persistent data-guard verification and transaction `before_commit`.

New exact ledger protection checks occur in the constructor and `verify` entry, querying `sqlite_master` definitions ([storage:314](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/storage.py#L314), [storage:490](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/storage.py#L490)). They were not added to each `post`. New initialization gate/actor checks run at transaction boundaries; during offline bootstrap no owned initializer is active, so their registry checks return through the empty fast path ([startup:30](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/startup.py#L30), [startup:80](https://github.com/PureGamma-Harness/uta-unified-account/blob/763202df9cb3ce089721e5281371aff3eab58089/uta/startup.py#L80)). This is not250000 newly added schema/history scans.

Existing per-post `PRAGMA database_list`, path/joinability validation, SQL/savepoint/hash work and977 real transaction commits can accumulate substantial fixture cost. AST equality does not prove equal elapsed time, and no phase CPU/I/O evidence identifies the dominant cost here. We therefore do not blame a particular refactor, schema check, SQLite stall or host scheduling effect.

## Proposed phase instrumentation: NOT_RUN, root approval required

A future small phase experiment should preserve arguments/results/exceptions and record new instrumentation/code-artifact fingerprints. It must not patch clocks, TTL, guards, verification results or financial state. These observations should be written immediately to a separate JSONL, not kept only in a final summary:

1. Outer/source import and environment/provenance begin/end, plus initialize call begin/end. These are part of total harness cost even when outside the existing `initialize_ns` field.
2. Bootstrap begin, account-creation end, each batch COMMIT return/count, and bootstrap end. Count real successful batch returns; a thrown commit stays failed/unknown. Do not log a posting result as a committed batch.
3. Native ledger and spot preflight begin/end, funding reconciliation, queue/fence sealing and `initialize.return`. Do not include private writer nonce/auth data.
4. Independent initial reference begin/end, durable enqueue begin/end/query, worker spawn/owned replay/READY, close request, final reference begin/end and cleanup completion.
5. On exceptions/signals, first persist the current phase and error category. If unchanged finally begins a long verification, record that new phase before calling it. A missing end remains partial evidence, never a fabricated completion.

Each event needs phase/call/parent IDs, PID and thread identity, UTC/monotonic/boottime, cumulative user/system CPU, peak RSS and committed-event count where relevant. Capturing these counters is observational; new overhead belongs in the measured configuration. An outside watcher should own only the new descendant tree and retain the same bounded timeout/pidfd/subreaper rules. Source, runtime, all loaded wrapper identities, actual CID, exact heads and full reference results remain required.

For a separately authorized small bootstrap profile, restrict profiling to the naturally single-threaded fixture-generation stage. Verify expected counts: `post=N`, seed commits=`ceil(N/256)`, complete-history verifies **inside bootstrap=0**. This could distinguish per-post codec/SQL/path work from transaction or native preflight cost. It must not profile mixed keeper/background threads as if cumulative times were disjoint CPU percentages. It is not an authorization to run a new small or large case now.

## Separate future experiment scopes without changing this result

| Future scope | Explicit timing boundaries and retained costs |
|---|---|
| Fixture generation | First bootstrap mutation through last confirmed seed batch COMMIT; retain event/transaction counts and its full resource cost. |
| Offline initialization | Full public `initialize` call, including fresh schema, bootstrap, native full validation and sealing; separately retain initial independent verification. Do not subtract missing phases from this failed run. |
| Prepared-fixture owner start | Only after a new, fully validated private fixture is declared prepared, time normal router start through matching live-token READY and original-CID terminal. Keep preparation and all before/after reference costs as separate evidence. Native worker full replay remains enabled. This is not yet crash recovery. |
| Actual crash recovery | Require an earlier actual READY owner, then record a genuine supported crash/death event and replacement ownership/generation. Time death/request, next acquire, READY and durable command completion separately; include ordinary lease waiting. Without the earlier owner and actual crash, do not call it crash-recovery RTO. |

A prepared fixture must retain its canonical authority path; copying or moving a managed DB is not a valid way to get a new ready authority. A later verified warm-fixture result would be a **new case with a different scope**, not a replacement PASS for this60s failure. The current partially observed authority cannot be relabeled prepared merely because its head matches. Any new validation/profile/fixture preparation, budget or crash experiment requires an explicit new root-approved registration and quiet window. No service,6h soak, financial trade, sustained-capacity or HA claim follows from this proposal.
