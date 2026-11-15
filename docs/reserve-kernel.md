# Exact order reserve memoization

This is an opt-in calculation optimization for the existing authoritative linear
USD perpetual order path. It authorizes no new product, account mode or trading
operation. The default `ExchangeService(..., reserve_cache_size=0)` retains the
original `_reserve_reference` Fraction formula. Set, for example,
`reserve_cache_size=4096` to reuse pure reserve results. The accepted integer
range is 0 through 65536; booleans and nonintegers are rejected before database
file creation. No schema or persistent-policy migration is needed.

Each service owns a thread-safe, bounded LRU. Nothing is shared globally or
persisted. Its immutable key contains every value used in the calculation:

| Input | Meaning |
| --- | --- |
| quantity, filled_quantity | Signed order quantity and signed cumulative fill, in base units |
| limit_price, mark_price | USD per base unit |
| reduce_only | Whether IM is omitted under the existing order policy |
| initial_margin_rate | Effective margin rate resolved from the current product policy |
| fee_notional | Cumulative executed order notional in USD |
| charged_fee | Cumulative already charged order fee in USD |
| fee_rate | Current configured order fee rate |
| usd_scale | Settlement precision used for the cumulative fee ceiling |

Keeping both quantity components avoids an ambient Decimal subtraction before
lookup. Decimal keys compare by exact numeric value, so representations such as
`2` and `2.00` may share an entry. The mathematical result is identical. Account,
order, market and policy version numbers never stand in for actual values.

For remaining quantity `r = quantity - filled_quantity`, the result is the sum
of IM, adverse execution loss, and the unpaid cumulative fee:

- IM is zero for reduce-only orders; otherwise
  `abs(r) * max(mark, limit) * initial_margin_rate`.
- Adverse execution loss is `max(0, r * (limit - mark))`.
- Fee is `ceil_to_USD_unit((fee_notional + abs(r) * limit) * fee_rate) - charged_fee`.

All intermediate arithmetic uses exact rationals and integer ceilings. Decimal
construction does not depend on the caller's precision or rounding traps. The
original service expression remains separately callable for same-source A/B.
Independent acceptance must also use a separately developed reference model;
comparing two implementations in this module alone is insufficient.

The separate [market decoder cache](market-cache.md) is integrated through
`market_cache_size=0` (default) or an explicit capacity up to 64. It replaces
only decoding of the complete payload read by the current transaction. Market
freshness and configured-policy checks remain after decoding on every use.
`market_cache_stats()` and `clear_market_cache(reset_stats=False)` expose its
own independent diagnostics and lifecycle. Both cache-size arguments are
validated before any database file is created.

The service still reads current authoritative rows and current market data. It
resolves outstanding-order product eligibility and effective IM on every call,
including cache hits. Existing market-age, configured-market-policy, balance,
liability, position, reduce-only allocation and admission checks run as before.
The cache never stores account risk, available margin, acceptance decisions,
aggregate reserves, transaction results, database rows or connections. A warm
entry cannot hide a changed field behind an unchanged account/market version.

An aborted transaction may leave a pure arithmetic entry behind. It has no
financial authority: the next operation rereads committed rows and derives a
new complete key. Restarting, evicting or clearing entries changes only work
performed. Cold calculations run outside the cache lock; concurrent cold calls
can calculate the same result twice. Failed calculations are never inserted.

`reserve_cache_stats()` returns `capacity`, `size`, `hits`, `misses` and
`evictions`. They are process-local calculation diagnostics, not counts of
durably accepted orders. The service's disabled original reference path does
not touch the cache counters. `clear_reserve_cache(reset_stats=False)` clears
entries; `reset_stats=True` also resets counters. A calculation already running
during a clear can subsequently repopulate the cache. Snapshot counters before
and after a timed workload to keep setup traffic separate.

## Deployment, verification and rollback

Use synthetic or authorized data. Start with size zero and record the source
SHA, configuration and raw outputs. Run the same workload with an explicit
nonzero capacity. Separately report computation, actual durable admission,
matching-confirmed settlement and any queueing. Reopen storage using size zero
and reconcile orders, positions, cash, fees, events and ledger hashes. Cache hit
rate is evidence of reused calculation only; it proves no capacity or latency
target. This change makes no production, HA or 10,000-per-second claim.

Run `python -m unittest discover -s tests -p 'test_reserve_kernel.py' -v` for
local bounds, key-completeness, manual-case, original-formula comparison,
low-context, concurrent-access and restart checks. Independent financial and
fault suites exercise the same public service separately.

For rollback, stop admission and drain existing writers under the normal
service procedure, restart with `reserve_cache_size=0`, and run reconciliation.
There is no cache state to migrate or restore. Do not roll back committed
trades or ledger entries as part of disabling this optimization. Rules and
market outages retain their existing rejection and cancel behavior.
