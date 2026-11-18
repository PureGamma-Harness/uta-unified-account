# Exact reserve reuse: bounded opt-in candidate, not production acceptance

Status: CODE only, no new target execution, import, compile, SQLite, benchmark or monitor registration. Source starts at SAFE `13a25363ede7fcfcd61d0b1f33b1b539ca9e3cab`; all 61 native UTA files remain runtime `a2434bdfe711ead1d202f6c1527e527f73e2dfa2`. This experiment does not use later product/risk changes. Independent review of the existing six-authority raw evidence is SAFE `f3fb0b707421f99110e0984b5ffe5fa7255459df`.

## Evidence and smallest candidate

`evidence/reviews/matching-component-profile/reserve-reuse-candidate/stored-profile-hotspots.json` extracts existing, sealed JSON reports by byte hash, without opening any database or loading the target. In the single 128-order scan batch, wall time was 358.133 ms; `_reserve_reference` ran 2,872 times (31.114 ms self, 200.878 ms cumulative), `_risk` 48 times (248.750 ms cumulative), and Fraction construction 43,850 times (86.449 ms cumulative). Nonoverlapping Fraction self time was 118.437 ms, book selection/ordering 4.984 ms, and SQLite native execution including commit 30.561 ms. Cumulative times overlap; these values must not be summed. COMMIT/fsync is not separately identified.

The candidate explicitly constructs the existing `ExchangeService(..., reserve_cache_size=128)`; its unchanged default is 0. This reuses the existing exact Fraction `ReserveKernel`, rather than adding another numeric model. `_reserve_reference` remains the reference path. Both sides use native scan matching, market decode cache 0, native UTC clock, default quote TTL 5 seconds/future skew 1 second, fee .0004, USD scale 8, decision audit, and SQLite WAL/FULL. No runtime function is overridden.

The new `--reserve-reuse-pair` entry runs only two fresh 32-order synthetic authorities, reference0 then candidate128. It cannot fall through to the old full six-database profile, setup-only, old scan baseline, aggregate or retry. Each side uses the same seed, two accounts, deposit, quantity/price sequence, genuine quote cadence, FIFO reference, and one eight-match call. One observer spans both authorities and closes in `finally`; cProfile, local LINE and SQL callback costs apply symmetrically. Serial order/cache/host effects and one sample prevent significance or regression claims.

## Economic key and validation order

`ReserveInputs` is the complete pure-arithmetic tuple:

| Input | Meaning |
|---|---|
| quantity, filled_quantity | Signed original and already filled quantities; remainder is exact Fraction subtraction |
| limit_price, mark_price | Current limit and current resolved mark |
| reduce_only | Removes order IM only, not adverse execution loss or unpaid fee |
| initial_margin_rate | Current instrument or configured product-tier IM |
| fee_notional, charged_fee | Cumulative filled notional and already charged fee, including rounding residue |
| fee_rate, usd_scale | Current fee policy and settlement unit |

Product ID, account ID, clock, quote version, rule ID and MM are not inputs to this pure formula. Equal numeric Decimals can reuse an amount; this is not reuse of an authorization or risk decision. Each positive-capacity `_reserve` first reads current order quantities, resolves the current instrument (missing => `market_incomplete`), then resolves configured product eligibility, requires linear perpetual/multiplier 1, and resolves its current IM tier (unsupported => `unsupported_product`; missing supported rule => `risk_unavailable`). Only then may it call the cache. The capacity0 path retains the original corresponding checks and Fraction expression.

The service still acquires its native transaction and any configured Database fencing guard; admission/matching still read current account state, validate market freshness/policy, calculate full risk and fees, persist audit evidence, settle ledger and positions, and commit. No financial decision, database connection, account balance, lease token, product object, quote or whole-risk result is cached here. Informational `account()` already uses `fresh=False`; this candidate does not turn that read into a fresh admission proof. The proposed legacy authority has no writer token, so this pair supplies no new lease/fencing, concurrent-admission or distributed-writer evidence.

Audit archives the exact execution option in its policy payload. Candidate128 and reference0 therefore have different policy IDs; the runner checks the complete explicit policy schema, exact `{reserve_cache_size: capacity, market_cache_size: 0}`, and exact remaining policy fields plus identical runtime artifact ID. It does not erase those policy differences from raw reports. Existing finite provenance exceptions are only quote `observed_at` and order/match `created_at`; complete raw quote payload/ID/SHA and risk time remain, with each quote checked independently against native TTL. All other economic projection fields, all nine non-temporal legacy risk fields including account/market versions and ratio, quote financial fields/version, and account views must be typed/canonical exact. No unknown risk or policy field is ignored.

## Human oracle and limits

Let r = quantity − filled; L = limit; M = mark. Reserve = (reduce-only ? 0 : |r| max(L,M) IM) + max(0,r(L−M)) + ceil_to_unit((prior_notional+|r|L) fee_rate) − charged_fee. Ceiling is cumulative, not a fresh fee ceiling per partial fill. All finite decimal inputs are rational with factors 2/5; multiplication/addition and integer fee ceiling are exact, and terminating Decimal construction ignores ambient precision. Required error is exactly zero; no tolerance or approximate comparison is permitted.

Unless stated, quantity=1, filled=0, L=M=100, IM=.1, fee=.0004, prior_notional=charged_fee=0, scale=2:

| ID | Change | Exact reserve / expected policy |
|---|---|---|
| R01 | baseline | 10.04 |
| R02 | q=2, filled=.5, L=110, prior=25, charged=.01 | 16.5 + 15 + (.08−.01) = 31.57 |
| R03 | L=101 | 10.1 + 1 + .05 = 11.15; scale8 instead gives 11.1404 |
| R04 | L=102 / M=100 | 12.25 |
| R05 | L=101 / M=120 | 12 + 0 + .05 = 12.05 |
| R06 | q=−1, L=99 | 11.04; reduce-only gives 1.04 |
| R07 | filled=.99, prior=99, charged=.04 | .1; paid fee ceiling residue is not charged twice |
| R08 | filled=1, prior=100, charged=.04; or q=0 | 0; native admission still owns rejection of a new zero order |
| R09 | pure q=0, charged=.01 | −.01; synthetic overpaid arithmetic only, not an authorized refund/order |
| R10 | baseline L=101, IM=.2 | 21.25; new IM is in key and must miss |
| R11 | capacity2 access A(100), B(101), A, C(102), B | values 10.04,11.15,10.04,12.25,11.15; hits1/misses4/evictions2/size2 |
| R12 | same values with different Decimal spelling | exact same result; numeric-equal key hit allowed |
| R13 | product changed to inverse/option, multiplier2, absent product/tier | configured native guard must reject before kernel even after an economically equal warm entry; not exercised by the legacy two-authority benchmark |
| R14 | fresh quote version/asof changes but all numeric inputs equal | amount may hit; a stale/incomplete quote must still fail in the native fresh-risk path, not use the amount as authorization |
| R15 | MM-only .05→.1 with unchanged IM | pure order reserve unchanged; full portfolio MM must change; MM is not part of this formula |
| R16 | configured rule ID/version changes | current catalog/policy checks remain authoritative; a persisted incompatible policy rejects configuration change, not a cache hit |

Example for R15 at scale8: cash/equity 999.96 after buying position1@100 with fee .04; pending buy1@101 reserves 11.1404; position IM10, MM5, available978.8196, ratio199.992. Changing only MM to .1 implies MM10, same order reserve/available, ratio99.996. Moving mark to120 instead implies equity1019.96, position IM12/MM6, order reserve12.0404, available995.9196. These are hand policy expectations, not new native results. Existing `tests/test_kernel_reference.py` covers configured rules/product, freshness and changed market payload; `tests/test_kernel_faults.py` covers cache/commit failure and concurrency; none are rerun or newly claimed passed by this CODE delivery. Configured PM/Cross, options, inverse/multiplier contracts, borrowing, expiry, fee/rule migration and mode changes remain outside the two-authority experiment's acceptance scope.

The four new pure contracts independently express the rational formula, check the hand values, mutate every economic-key input, count deterministic eviction, test hostile Decimal context, and preserve failure without cache insertion. They import only the existing reserve module, not service/SQLite; they do not prove policy eligibility, TTL, transactions or durability. All are NOT_RUN pending separate review and root GO.

## Proposed acceptance, deployment and rollback

The separate frozen plan binds exact source/manifest, the four arithmetic methods, and one native fixed pair. Native acceptance requires actual cache statistics: reference service bypass counters stay zero; candidate setup has six distinct initial economic keys, size=misses=6/hits>0/evictions0. During the eight-match batch, candidate must record hits>0, new misses in [0,16], size≤22 and evictions0. These bounds follow the six initial keys plus at most one new remainder key per one of sixteen fills; they are diagnostics to verify, not inferred results. Reopened counters are recorded from a new kernel with the same configured capacity. A capacity flag alone is never evidence of reuse.

Each authority must have eight independently ordered unique trades within its own namespace, sixteen paired fills, joint commit, hand cash/fee/quantity/cost checks, full typed financial before/after reopen equality, strict Matcher verification, independent cashflow reconciliation, and one archived FILL numerical replay. Across the pair all listed financial fields must exactly agree. A complete trace/monitor lifecycle is required in each phase; first fault, stale quote, partial completion, timeout or unknown outcome stops the whole pair with original evidence and no retry/quote republish to repair it.

Deploy only the benchmark controls on an isolated synthetic workspace. No API/CLI/worker/product activation or production-default change is shipped. No schema/data migration is needed. Production activation, multi-node capacity, fault recovery, open-loop 10,000/s, 30-minute/soak and liquidation acceptance remain unproved. Even a faster pair supplies only a candidate for a separately reviewed workload/long-run experiment.

Rollback of this delivery is removal/revert of these benchmark controls and plans; runtime remains unchanged/default0. Preserve all completed audit records, trades, postings and raw originals. An operator considering an existing audited authority must restart with explicitly reviewed options and retain archived old policy IDs; never edit persisted risk/fee/scale policy or audit rows to force a rollback. This experiment instead uses fresh isolated authorities and leaves both intact for reconciliation. Any DB/WAL/SHM, actual nonce, complete capsule or full private archive stays local/private; only a reviewed whitelist of summaries/hash and permitted original streams can enter a later SAFE public commit.
