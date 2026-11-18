# Independent risk and liquidation CODE review: 90e81daa

Reviewed immutable source `90e81daa7b7cb398664c1dadb3a0d943e45321d6` against local
fresh-authority USD funding obligations. This is source, AST, JSON, byte and
independent hand-arithmetic review. No target module was imported or compiled;
no test, SQL, thread, worker, process inspection, benchmark or CI was executed.
The six future methods remain **NOT_RUN**. The source is not approved for real
funds or production.

**Disposition: limited CODE closure; no confirmed additional local-contract
blocker.** FUND-OBL-001/002 close their specific source paths, with the
public-publisher limitations below. A proposed third candidate was rejected
during final full-call-chain review because public publication always requires
the USD settlement quote. No financial source change is requested from that
candidate. Runtime acceptance and real-funds release remain OPEN / NO_GO.

## Frozen inputs and review boundary

The independent byte check verified all 66 physical input files, totaling
1,414,749 bytes, against `runtime-inputs.json`, SHA-256
`8653d8976cc7b3191fe14600a21579aac2de8cea107ce1b40d9b42228fecde98`.
The manual plan SHA-256 is
`4c5b959b12437f53b38474cdd112eabb5529151c93a937f17d951e2fd667e36f`.
The obligation module is 63,141 bytes, SHA-256
`13e3f7d35b2aeefdb8bb5852280bb2cb65e40c3a62858ec4cc37b4fc3eb51e97`.
The three retained original-901 plan/manifest/preparation copies matched their
recorded byte hashes. AST parsing was limited to the two funding modules and
the new test source; it was not target compilation or execution.

This review covers the native unbound SQLite authority, configured Cross,
USD-settled multiplier-one perpetual funding. The capability does not restrict
account collateral to USD: `FundingLocal._native` accepts any otherwise valid
configured Cross catalog/rules, and `_trading_policy` freezes all asset scales.
That distinction is material to FUND-OBL-003. No REST, automatic due timer,
managed fencing, old-binary exclusion, custody, HA or production claim is made.

## Rejected candidate FUND-OBL-003: public USD settlement guard

A candidate considered whether pre-payment USD=0 could permit a current market
without a USD asset quote, followed by the funding leg creating nonzero USD
and a recoverable risk error after preflight. The full public call chain
**excludes that construction**: `publish_market` calls
`_validate_market_command` at `uta/service.py:663`; lines 654-656 unconditionally
require USD price=1 and collateral_factor=1, before the inventory-sensitive
`_publish_market` checks. The public snapshot cannot omit USD even when every
USD balance is zero and no USD borrowing exists.

The initial candidate considered `_publish_market` in isolation. This was an
incomplete reachability assessment, corrected before this review was committed.
It is not a confirmed finding or reason to modify the financial source. The
reviewer notified the integration owner when the candidate was considered and
again immediately when the earlier public guard disproved it. No target case
was run, and no source or acceptance plan was changed to reproduce it.

A partial stored snapshot obtained through corruption or bypassing the public
publisher is a separate fault-model question; it is already OPEN and has no
public-path acceptance claim in this slice. It cannot substantiate the rejected
candidate as a normal public-path blocker.

## Limited source closures

- FUND-OBL-001: `_require_mark` checks product/margin eligibility, then the
  actual missing required instrument key, before indexing the boundary mark.
  Its precise ServiceError reaches WAITING_DATA without a cut or money.
- FUND-OBL-002: current already-held positions, live-order reserves and native
  asset/deficit quotes pass through the new preflight classifier. It checks
  the wrapped PortfolioError or exact live-order KeyError and confirms the
  missing snapshot key. Other errors retain rejection/REVIEW. This closes
  the original already-held-inventory path. It is not an executed fault-recovery result.
- The real publisher rejects removing a live BTC position/order quote.
  The revised capture fixture publishes USD-only before positions exist. The
  current-data helper negative control does not persist a partial snapshot or
  prove recovery of a corrupted persistent market. That integration remains
  OPEN. After genuine full closing trades, a USD-only current snapshot is
  legal and must not be rejected solely because the historical cut used BTC.
- Capture reads actual rows, account versions and event watermark under the
  same BEGIN IMMEDIATE writer as its immutable cut. The cut is the actual
  logical sequence observed within the lateness policy; it does not prove
  historical UTC-end holdings before that sequence. No cut after the window
  is fabricated from present positions.
- Cash is taken from the stored cut, while current native risk, original
  supervisor cancellations/reduce-only planning and final fresh-market
  identity are used at apply. The code does not mark orders as fills or remove
  exposure because an unfilled liquidation order exists. Cash, supervisor
  changes, receipt and terminal state share the outer financial transaction.
- Claim generation, owner, private nonce and canonical expiry are compared
  under the serialized writer, with another observed clock check after the
  financial work. Replayed command results return before creating new effects;
  receipts and product/period identity prevent a second payment. This does
  not promise physical COMMIT/fsync before expiry, exclude arbitrary old
  binaries, or prove a cross-host lease. Clock observation rollback rejects;
  unobserved clock failure and HA remain outside the proved assumption.
- WAITING_DATA/CAPITAL and REVIEW keep the cut and outstanding task. Command
  IDs are global in the capability and content checked; original command
  query is available after an unknown response. A missing read result alone
  cannot authorize a new economic obligation or prove an in-flight commit
  will never appear.
- Capital verifies a treasury-owned confirmed USD deposit and its real
  custody journal, rejects used proof, requires unreserved settled cash and
  no treasury trading/debt, and transfers actual cash to the segregated
  reserve. Customer legs, clearing and variance are explicit balanced journals.
  Principal/interest are not fabricated from negative funding cash. The
  original Cross calculator includes cash deficits in debt, and the original
  supervisor handles MM/BANKRUPT/BLOCKED consequences using confirmed cash.

These are CODE conclusions under the stated immutable-code, trusted-clock,
native-writer assumptions. `verify()` explicitly returns
`risk_eligibility_replayed: false`; its journal reconciliation is not an
independent replay of each supervisory eligibility decision.

## Independent hand calculations and unexecuted gates

Normal case: 1000-.04-.01=999.95 and 1000-.04+.01=999.97. The delayed case
genuinely closes at 101: a=1000-.04+1-.05=1000.91 and
b=1000-.04-1-.05=998.91, then frozen -1/+1 makes both999.91. Flat current
positions have IM=MM=0 and no historical BTC price requirement; USD price is
still required for their nonzero current USD cash.

The three-account rounding case has q=.4/-1/.6 at mark1/rate.015. Exact cash
is -.006/+.015/-.009, toward-zero cents 0/+.01/0. Treasury transfers .01 to
reserve, the customer receives .01 and reserve pays the .01 variance; clearing
and reserve return to zero. No principal is created. Opening/additional fees
are .07/.04/.03, so customers end999.93/999.97/999.97 and treasury .99 after
its real1 deposit.

The independent risk hand oracles also explain the coverage limit: normal
mark100 has risk equity999.95/999.97 and MM5 each. The refreshed mark101 case
has equity1000.95/998.97 and MM5.05 each, despite cash999.95/999.97. Capital
mark1 has equity960.33/1098.97/940.57 and MM.02/.05/.03. These fixtures remain
well above maintenance; they do not demonstrate a distress transition.

Independent fixture accounting gives planned per-scenario journal counts
normal6, missing4, current-data6, capital11, competition6, changed-positions8,
new-empty0, old-empty0, review5: total46, including the intentional orphan.
The same source gives 9 authority-qualified matches/18 fills, fees .72,
custody -15001, 8 obligations/5 APPLIED/3 outstanding. These are **planned
hand oracles**, not observed outcomes or throughput. Business IDs repeat across
the independent namespaces. The orphan namespace must fail healthy full
verification; readable REVIEW does not make it financially healthy.

The six fixtures do not exercise a funding debit actually crossing MM, creating
a deficit, or changing a current loan-only state. Source tracing supports the
intended call chain, but funded-threshold, debt/deficit and supervisory-state
acceptance evidence remains OPEN. The future two-thread contention fixture is
unexecuted and does not prove sustained concurrency, commit/crash recovery or
wallclock lease precision. Pending funding also remains outside order,
withdrawal and transfer reservations. Those are explicit separate production
gates, not hidden approvals from this review.

Deploy only to a new isolated synthetic authority after independent entry
review and the bounded execution gate are resolved. Rollback stops explicit
invocation and retains tasks, cuts, command results, claims, receipts, journals
and events. Never delete the marker/tables to hand the authority to an old
binary. There is no approved live-data migration or real-funds rollout.
