# Matching snapshot selector: independent CODE closure

**CLOSED: no remaining concrete CODE blocker within the stated native domain.**
Target source: `26fa6285afde7d38e8e811f54ac16e5816fdd79d`.
Source-plan/materialization OWN: `0006564881af066a6bd25840dbdc83b896244461`.
Base: `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`.
The review used Git and text only; no Python import/compile/execution, SQL,
test, process, signal or network operation was performed.

| Frozen input | Bytes | SHA256 |
| --- | ---: | --- |
| `uta/matching.py` |29761| `b308516497d690ec1ac53056e27bd64afcd0c13ea7ee7c49f337983377af98d9` |
| `uta/service.py` |85864| `9c68ee82b07b66d5272cb820399c7bf6971759bfe1497acf46ac839e95ba7034` |
| `tests/test_matching_selection_snapshot.py` |19870| `f379016c70bf3d9ae141314801cc2aeacb8c4d2d8e6faa4c9f78f083dcc328dc` |
| `evidence/reviews/matching-selection-snapshot/run_once.py` |6807| `e07928d9fbf59bbfc33157c12e1bd3d1d59abccc88a9722ae819fa7d67c7d15a` |

The four SHA256 values match the reviewed files and final plan. Runtime changes
are limited to matching.py (144 added/10 removed lines); service.py is unchanged.
The default remains scan. Snapshot is an explicit constructor option with no
worker, CLI, HTTP or persisted configuration activation.

The selector preserves exact Fraction price and rowid priority, snapshots only
the inventory/order, and reloads a full row by its primary key on every peek.
It never caches market, account risk, reserve, fee or settlement results. Native
fills reduce remaining quantity; native reduction invalidation and STP/rejection
cancel orders. Point reloads detect those cancellations and partial fills.
The new selector is outside the unchanged two-leg savepoint block: no head is
advanced while either leg can be rolled back. A second-leg ServiceError restores
first-leg fills and collateral cancellations before the next peek. Unexpected
exceptions still abort the encompassing transaction. Fee, trade identity, maker
price, audit/receipt creation and both authorization legs are unchanged.

Snapshot requires exact native service/database/ledger/audit objects, the finite
reviewed entry bindings, one authority and the original default clock metadata.
Unknown subclasses, relevant overrides and custom service/fence clocks are
rejected. Both ProductCatalog and PortfolioRules must be None, closing their
public model-dispatch boundary for this first scope. This is a finite supported
domain, not a same-UID Python sandbox. Same-transaction insert/amend/reopen,
custom SQL callbacks/triggers and new extension callbacks remain unsupported;
head checks are not a detector for all changes to nonhead rows.

The fixture executes selected real selector/guard AST with memory rows and inert
component stand-ins. The expected selection independently rebuilds and sorts the
current candidates on every peek, using exact Decimal comparison/copy_negate and
rowid rather than the production Fraction priority key. Two review findings were
corrected without execution: constructor declaration defaults now receive
timedelta/Decimal, and a same-price input with reverse rowid order tests both FIFO
heads explicitly (1,3), then checks the subsequent heads after cancellation.

The12 methods retain the256 seeded twelve-step traces, RO cross-cancellation,
partial fills, rollback-before-peek and STP state models, transaction lifetime,
unknown component/clock refusal, scan compatibility and the market-unavailable
early exit. Settlement transitions are explicit memory models; only that early
match_once branch is executed. They do not prove actual _apply_fill settlement,
SQLite locking, fees, risk, two-leg rollback, or reconciliation. The128-row/
20-iteration count case measures adapter calls, not SQL plans, time or throughput.

The frozen driver selects exactly12 methods, validates four input lengths/hashes
before and after, and forbids native imports/effects. The ten-second line guard
does not make blocking OS calls hard real-time. Stdout/stderr and both fallback
streams share256KiB, reserving each UTF-8 request before FD writes and keeping512
bytes for one emergency trailer. Partial/failed writes retain their reservation,
latch failure and self-exit125. The frozen fixture has no native FD emitter; no
fsync guarantee is claimed. Interpreter startup/preparation failures are separate.

The final plan remains a single proposed one-CPU/ten-second/at-most384-scenario
pure scope. Earlier source plans retain NOT_RUN/zero-attempt status. This CODE
signature supplies neither execution authorization nor a pure/native PASS.
Root's subsequent explicit scope governs any first run. Real SQLite differential
matching, settlement/reopen checks, concurrency/faults, performance and production
activation remain NOT_RUN/NO_GO; the optimization remains default OFF.
