The matching loop repeatedly reads and sorts the full limit book. This adds an explicitly opt-in transaction-local exact priority list while re-reading each selected order's current state. `Matcher(exchange)` remains scan; snapshot rejects unsupported components, custom clocks and configured policy models. Financial pricing, risk/fees, both settlement legs, savepoints and commit rules remain unchanged. Worker/CLI activation is absent.

The published source qualification is C `a2434bdfe711ead1d202f6c1527e527f73e2dfa2`. Its first attempt1 outcomes remain separate:

| Qualification | Run | Python3.10 |3.11|3.12|3.13|
| --- | --- | --- | --- | --- | --- |
| Exact-head push |44241282705|FAIL|success|success|success|
| PR-event / separate merge ref |44241334703|success|success|success|success|

The failed push original records2061 tests/1FAIL/0ERROR/0skip, 367 source hashes matching C, and all12 new selector IDs individually ok. The unique failure is the bounded SH capture precondition at `test_durable_faults.py:1461`, before the later five-second recovery assertion. Its cause is not established as a matching regression. PR green is provider job-metadata qualification, with no successful PR-unit originals downloaded. Original unit ZIP/three members and connector-decoded job log are preserved; the old private zero-byte download is not substituted. Independent CI closure1324309 confirms these bindings. One successful exactC push3.11 package report records seven checks and isolated8 tests/eight commands; this is report-only, without wheel/sdist payload download, and does not turn the push matrix green.

Separate first evidence:

- Source26fa628: unique selected-AST memory run12/12, CPU[0], four inputs unchanged; independently verified by5fa9400. Component operation counts are not SQLite/TPS measurements.
- Source3b0c49a: one actual native SQLite run, four cases × scan/snapshot, eight fresh synthetic authorities. Each mode separately completed six actual matches/twelve fills. FIFO/STP/partial fills, RO cross-cancel, real second-leg account_frozen rollback and no-liquidity/halt/resume passed. All eight authorities reopened with exact financial projections, complete ledger hashes/postings and strict matching/independent cashflow replay; six nonempty authorities each retained one actual FILL numerical replay sample. IDs intentionally repeat across authorities and cannot be aggregated as global unique throughput.
- Independent7cd908a verifies the actual captured rows and source/output bindings: SCOPED_ACTUAL_SQLITE_EVIDENCE_PASS. Its additional five-field JSON valuation reader is separate from those six producer-executed replay samples. The reader's first incorrect RO adverse-loss waiver is preserved in69b4958; only its reference line changed, and the trading target was not rerun.

The SQL driver ended in10.144206064011087s. Outer lifecycle monotonic timing was not captured; this is not E2E performance. Its monitored logical size8,602,820B does not prove a kernel quota, unsampled C-write peaks or hard I/O deadline. Actual Python3.12.14/SQLite3.53.1 used builtin `_sqlite3`, null extension path/SHA, and NOT_OBSERVED loaded libraries. All63 original/mini-source hashes match;18 loaded UTA origins are recorded. Full first reports/logs remain; database binaries, native journals, private transport headers and token references are excluded.

This supplement preserves author commits via merges and uses [skip ci]. UTA, original tests, build and CI configuration are byte-identical to C. Added control/reader/evidence paths are statically selected by the existing MANIFEST patterns; no package build/install or CI rerun was performed for this supplement. The current package qualification therefore remains scoped to C. See `docs/matching-post-delivery.md` and its per-file integrity manifest.

No schema/data migration or production mode activation. Rollback retains financial history and all first evidence and restores default scan; never downgrade guards or hot-swap an active writer. Configured products, managed/concurrent writers, HA/custody, actual USDT/USDC, first-batch spot/loan production acceptance, sustained capacity/10k/s and real funds remain NO_GO. No performance improvement or production approval is claimed.
