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
| Read-only JSON aggregation |10s|8MiB|15KiB|
| Root host records/captures |remaining5s intended|2MiB|1KiB|

The total is at most120s of the planned active sequence,128MiB logical data
and512KiB raw. All phases use one allowed CPU and record its actual number.
The separate root host producer supplies a continuous outer timer; summing
target internal times does not establish a whole-call wall time. SQLite C I/O and the finite profiled
call cannot be interrupted by the Python line guard. Late or incomplete phases
are UNKNOWN/FAIL, never an accepted sample. File-length monitoring is not a
kernel quota and can observe C-side growth only at application boundaries.

Source files are copied0400 under0500 directories. Databases/reports are new
0700/0600 namespaces. Raw output reserves complete UTF-8 requests before direct
FD writes, retains reservation on partial/failure, latches failure and exits125;
each phase reserves512 bytes for one failure trailer. No warmup, retry, old
authority access, old suite rerun or deletion of a previous run is permitted.
Each target has no product workers, application children/new threads, network,
socket/TLS/AuthDB, explicit proc/PID/pidfd operations or signals. The separately
authorized host owns exactly two new target child processes; its only pidfd
handles and possible timeout signals address those children. It never opens
/proc or inspects or signals any pre-existing process. These are a
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
table economic equality; raw originals retain it. No *_at pattern is stripped.
The new uta_config and uta_liquidation_accounts captures use every raw column
and compare exactly outside the profiled window. Their schemas are respectively
{key,value} and {account_id,state,cycle,revision,plan_market_version,
plan_position_digest}; ordinary fixture liquidation rows are empty. All financial
fields, policy limits/state and complete ledger rows remain exact.

The native legacy-reference risk schema is exhaustively ten fields: account_version,
equity, initial_margin, maintenance_margin, open_order_margin, available_margin,
margin_ratio, market_version, observed_at, risk_mode. Unknown/missing fields fail;
configured policy risk dictionaries are unsupported here. Nine non-temporal fields
retain exact canonical JSON types and values. The sole risk exception is observed_at:
service._risk copies market.observed_at.isoformat(), so it is quote asof and never
calculation time. Fresh authorities necessarily have different real quote times.
Full original risks, actual current quote JSON, observed_at, archived payload,
market_snapshot_id and SHA remain raw. The quote's version/assets/instruments
compare exactly; only its asof and resulting content-addressed ID/SHA are separate
provenance. Each capture checks current and archived quote bytes in the same
transaction as native risk/fresh validation. Independent JSON aggregation repeats
schema/hash/reference/asof checks rather than trusting a stripped projection.
The recorded original UTC validation clock is sampled after risk; integer age is
computed from timedelta days/seconds/microseconds and must lie in [-1000000,
5000000] microseconds, including equality, matching native future skew1s and TTL5s.
This extra verification may fail; it never refreshes or retries a failed sample.
Setup already publishes once before every submitted order, with the same fixed
price/version sequence in all modes, so no new cadence or workload is added. Audit/source metadata differ between runtime C and B
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


## Continuous root host producer and finite receipt boundary

`benchmarks/matching_profile_host.py` is CODE only until root authorizes the exact
plan digest and both exact target argv arrays as one uninterrupted scope. It
creates two owned child targets sequentially, records real wait/reap/exit and
strict integer monotonic start/end/elapsed fields, and retains separate raw FD
captures. Missing handles, timeouts, late completion, incomplete raw or unknown
results stop the sequence. A held pidfd is obtained only for an unreaped child
created by this producer; timeout handling uses that handle, never a raw PID.
There is no capability probe. Missing required APIs reject before starting a
child. Each target is held at an explicit stdin FD0 startgate before main, UTA
imports or SQL. The host first records its own new child PID and closed gate,
rejects the fixed ten-number protected set before any pidfd/signal, obtains and
records a held pidfd, then sends exactly one G byte and EOF. A pre-release error
or protected number closes the gate without release, causing the new child to
exit on EOF. Only this owned child may be waited/reaped. Acquisition, signal or
raw-output errors unwind through gate closure, bounded own-child wait, UNKNOWN
receipt and held-handle closure; there is no naked-PID fallback or host raw-cap
os._exit. An OS failure obtaining a child handle is retained and cannot qualify;
blocked/unreapable C I/O has no hard realtime guarantee.

The JSON aggregate runs in the host interpreter through its explicit main
function, without a third child, UTA import, SQL or target-module replacement.
It checks both external phase receipts, exact argv, continuous scope context,
60/45s child limits,10s aggregate limit and120s total with at most5s of host
control overhead. Every integer rejects bool. End minus start must equal elapsed;
late, missing, incomplete or unknown cannot qualify. The external host then
records a completion receipt, invokes the aggregate's read-only final sequence
validator, durably publishes that receipt and checks the publication tail against
the same total/control budget. Comparison JSON alone is pending final host evidence.

Target receipts use actual_exit_status from wait(); the in-process aggregate
uses actual_return_status. The host cannot know its own future process exit and
records actual_outer_exit_status=null plus a mandatory caller observation. Root
must retain its actual host process exit0 and complete END event; an internal
return-status field cannot substitute. The measured sequence begins at host main
entry, includes plan reads, namespace creation, captures, receipts and aggregate,
and excludes interpreter startup before that entry. The final receipt's timestamp
precedes its own publication; the separately reported tail guard includes that
fsync/readback. The root tool's complete outer elapsed/exit remains mandatory.
Data-length checks remain logical monitoring, not a kernel quota. The host reserves
1MiB for the final receipt within its2MiB allocation and checks all four namespace
allocations and the joint128MiB bound. No setup, target, SQL or producer has run.

Controls53739d1 and final materialization3b28fa1, their exact old plan/manifests,
and earlier870 preparations are retained as NOT_RUN_ZERO_TARGET_ATTEMPTS. This
revision corrects an exact status mismatch and the explicitly identified quote
provenance comparison; it does not turn a prior attempted failure into a pass.

Before every new Popen and before aggregation, the host rechecks the same
continuous120s and control5s remaining budgets. It does not start another phase
after known exhaustion. Host stdout/stderr share a hard1KiB reserve-before-write
cap with sticky exceptions; aggregation is hard15KiB, sharing the original16KiB
allocation, so the joint raw cap stays512KiB. Controllercd7 was also never run
and is preserved as an unexecuted preparation snapshot, not a failed sample.
