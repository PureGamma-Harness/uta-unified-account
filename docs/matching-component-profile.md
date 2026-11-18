# Matching component profile: CODE only, no run or capacity claim

This candidate adds a bounded diagnostic, not a production performance gate.
Default matching remains scan. No runtime, account mode, risk rule, quote TTL,
fee, worker, API, authority schema or replication behavior changes.

The control starts at PR40 exact `a2434bdfe711ead1d202f6c1527e527f73e2dfa2`.
Its UTA tree is `05075e8b51c8b365e46a7f5f520a625a791fd6ad`, identical to the
already recorded functional source3b0. One current-target interpreter runs both
scan and snapshot in four fresh DBs.
A separately authorized interpreter runs original PR35 scan in two more DBs.
The latter uses a byte-exact capsule of PR35 matching.py and the same other60
UTA Python files. No process replaces imported modules or native methods.
Control source H, current runtime C and original runtime B are separate fields.
Only61 Python runtime files and the two target runners are copied per mini;
this is not a copy or validation of the complete old repository or wheel.

The first diagnostic budget is split before execution:

| Process | Time at checked boundaries | Logical run data | Raw Python streams |
| --- | --- | --- | --- |
| Current C, 32/128 books × scan/snapshot |60s|78MiB|320KiB|
| Original B, 32/128 books × original-scan |45s|40MiB|176KiB|
| Read-only JSON aggregation |10s|8MiB|16KiB|
| Root host records/captures |remaining5s intended|2MiB|included above|

The total is at most120s of the planned active sequence,128MiB logical data
and512KiB raw. All phases use one allowed CPU and record its actual number.
Root must supply the measured outer lifecycle; summing target internal times
does not establish a whole-call wall time. SQLite C I/O and the finite profiled
call cannot be interrupted by the Python line guard. Late or incomplete phases
are UNKNOWN/FAIL, never an accepted sample. File-length monitoring is not a
kernel quota and can observe C-side growth only at application boundaries.

Source files are copied0400 under0500 directories. Databases/reports are new
0700/0600 namespaces. Raw output reserves complete UTF-8 requests before direct
FD writes, retains reservation on partial/failure, latches failure and exits125;
each phase reserves512 bytes for one failure trailer. No warmup, retry, old
authority access, old suite rerun or deletion of a previous run is permitted.
The task has no product workers, application children/new threads, network,
socket/TLS/AuthDB, explicit proc/PID/pidfd operations or signals. These are a
reviewed-source/audit-hook boundary, not an OS sandbox or kernel attestation.

## Fixed synthetic workload and independent finance checks

Each authority has two accounts,1,000,000 synthetic USD per account, USD scale8,
one BTC-PERP instrument with mark100, IM.1 and MM.05, and original native UTC
clock/default quote TTL. Audit stays enabled and actual transactions use WAL/FULL.
The shuffled pair insertion order uses seed17023+book size. Buy precedes sell
inside each pair; each side has16 or64 orders. Quantities repeat1,2,5 units;
buy limits are100/101/102 and sell limits100/99/98. All assumptions are lab
policy, not exchange product parameters or a USDT/USDC production approval.

One native match_once(batch8) is profiled after exactly one fresh genuine quote.
There is no within-sample republish or retry until success. Partial completion,
stale market, rejection or fewer than8 confirmed trades invalidates the pair.
Setup submits each order under fresh native quotes and is separately timed.

An independent reference re-sorts current Decimal/Fraction price/time priority
on every expected trade. It derives maker price and canonical trade IDs without
calling production projection, fee, priority or identity helpers. Two hand cases
also pin31 units/3156 notional/1.2624 fee per account for32 orders, and40/4080/
1.632 for128 orders. These fees use original rate.0004 with USD8, opening-only
fills and full single fills per selected order: every calculated fee is exactly
representable in the minor unit, so no rounding residue occurs. This diagnostic
does not validate cumulative fee rounding or partial-fill fee dust; earlier
functional tests retain those separate scopes.

After return and actual financial COMMIT, each DB must have8 unique trade IDs
and16 corresponding fills. Cash, signed quantity/cost, every fill fee and zero
opening realized PnL are checked against hand/reference values. Reopening must
retain the complete ledger chain/postings, balances, positions, orders, fills,
versions and economic projection. Matcher.verify(strict=True), the existing
independent rational cashflow replay and one historical FILL valuation replay
per authority must pass. This last check is a sample, not all decisions.

Across paired authorities, only created_at on order/match rows is excluded from
economic equality; raw originals retain it. All financial fields and complete
ledger rows remain exact. Audit/source metadata differ between runtime C and B
and remain individually verified/retained rather than removed from raw DBs.
Business IDs intentionally repeat in paired authorities, so their sum is not a
global unique-trade capacity result. There are no liquidation fills in this plan.

## Profiler and SQL observation

Both modes use the same cProfile and nonmutating SQLite trace callback. The
callback records bounded category counts and no expanded SQL payloads. SQLite
can repeat trigger statements; these are trace events, not logical SQL calls or
transactions. Callback errors latch and fail the next boundary because SQLite
can otherwise swallow them. No native Database/Exchange/Matcher method is patched.

Matching wall time includes the native transaction, actual COMMIT, callback and
profiler overhead. The Python line budget trace is disabled only inside this
finite profiled call and restored in finally, so its per-line cost cannot be
misreported as a matching speedup. The phase deadline is checked before/after;
this expressly leaves no hard completion proof inside a blocked native call.

Full cProfile function rows are retained as JSON. Exclusive self-time groups
separate book ordering, risk/reserve, Fraction arithmetic, JSON, audit Python,
SQLite-native and control callback costs. Individual cumulative times overlap
and must not be added. Connection.execute C time includes SQL and commit work;
stdlib tracing cannot isolate COMMIT or fsync duration, so both separate duration
fields are null. COMMIT trace counts and post-COMMIT return/reconciliation are
different facts. No queue, network or cross-node handoff time is measured.

Four current-target samples compare current scan with snapshot. The separate
old-target samples are required to observe current scan versus original scan.
Mode order is scan/snapshot at32 and snapshot/scan at128; old scan follows in
its own interpreter. One observation has order/cache/cohost/profiler effects,
so no ratio proves statistical significance, absence of regression or capacity.
Batch time divided by fills is not a per-fill latency or percentile. All P50/
P95/P99/P99.9, open-loop throughput,30-minute and production flags remain unset
or false.

## Runtime, raw closure and recovery

The manifest pins exact Python version, interpreter SHA and SQLite version
from the prior runtime evidence. This run re-observes them before SQL and after
all work. The native SQLite module uses verified builtin or extension metadata;
builtin file/size/SHA are null. Loaded libraries remain NOT_OBSERVED because
there is no proc scope; no complete runtime attestation is claimed. Environment
records expose actual affinity, OS-reported logical CPU count, own resource
accounting and nofile limits. CPU model, physical storage, replication, network
and full hardware characterization are unobserved/not exercised; capacity
acceptance cannot use this component profile.

The JSON aggregator opens no SQLite or target module. It requires both external
root completion receipts, actual exit0/reap, exact argv, complete bounded raw
BEGIN/checkpoints/END and inventory-bound result/sample hashes. Receipts and
raw captures are outside both target-write namespaces. An inner PASS or missing
host receipt cannot qualify a failed/late process. Root receipts are ordinary
trusted orchestration records, not cryptographic remote attestation. Financial
equality uses canonical JSON bytes so bool/int/float aliasing cannot pass it.

Before root's specific GO, everything remains NOT_RUN. First raw bytes, partial
DBs, inventories, failures and unsupported-runtime metadata are retained without
repair or retry. Rollback removes these independent bench/control additions;
runtime and scan default were never changed. Existing code-bound authorities
cannot be swapped or their markers edited for this diagnostic. A later product
activation, performance optimization or long test requires its own frozen source,
profiles, actual correctness evidence and independent review.

The bench controllers install raw capture, tracing and argument execution only
under their explicit script entry points. Importing a controller as a module
does not replace the caller's streams/trace or parse its argv. Preparation
control870 and its manifests were never executed; their original JSONs remain
as named preparation snapshots when the entry-point guard was added.
