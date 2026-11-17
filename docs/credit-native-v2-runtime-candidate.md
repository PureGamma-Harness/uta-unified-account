# Internal synthetic V2 native runtime candidate

This is actual implementation, **not positive-chain or production acceptance**.
It is default off, fresh only, USD8/BTC8, zero new interest/fee, batch/cache0,
internal synthetic_local sources only. PREPARED1 never unlocks. No HTTP/CLI
activation or real-funds permission is supplied. The parent integration group
must run the first actual positive fixture on this immutable commit and retain
all failures; independent review retains veto.
Only sourced internal BORROW/REPAY and explicit halt/market metadata are in this
candidate. Normal trading, matching and liquidation adapters are not delivered
for V2. Generic acquire/CLI do not opt in; generic product readiness must remain
closed until those independent adapters and acceptance gates are delivered.

## Actual implemented boundaries

* `install_internal_credit_v2(database,exchange,credit,envelope)` uses the real
  original control transaction, validates unowned generation0/event1/unused
  inbox, actual original complete ledger/credit, source claims and immutable
  local budget. Non-BTC nonzero opening debt is refused. It creates exact
  catalogs, obtains actual code/policy evidence, inserts unique archives and
  metadata, then installs full SQL/writer gates and publishes marker/event last.
  Format1, prior owners, batch, partial schemas and replacement attempts refuse.
* `acquire_credit_v2(database,owner_nonce,ttl_seconds)` uses the actual internal
  fence path. That same control transaction performs original full financial
  verification before minting the real token. Generic acquire does not opt in.
  New services must come from the separate real read-only existing factory on
  `database.for_writer(token)`; old bootstrap objects are never rebound.
* Source, credit operation, business rejection and halt/market metadata scopes
  bind actual registry/connection/Database/role/PID/thread/token. Financial scope
  computes actual prestate, original journal head, quote/limits, trusted four or
  seven sorted legs and immutable intent before effects. No caller supplies
  expected legs or a successful verifier. Financial DML outside a real allowed
  scope and every runtime DDL attempt deny and poison the transaction.
* Twenty-two native SQL gates verify NEW/OLD/context data and actual staged
  intent/expected rows. Terminal success requires actual intent+credit receipt;
  credit closing requires the actual sealed full journal and complete dedicated
  borrow decision. Source+PENDING are one separate producer COMMIT; financial
  effects, audit, original receipt/event/version and SUCCEEDED share the later
  original Database COMMIT. UDFs perform no recursive SQL or observed counters.
* Before COMMIT reconstructs exact table deltas from an actual immutable start
  snapshot, including other accounts/orders/positions/receipts. Missing in-memory
  context still requires actual state equality, not an early return. Actual
  source/intent/ledger/debt/terminal/audit relationships close in both directions;
  original full ledger/credit/FK verification runs only after complete terminal
  obligations. Late validation errors latch fatal denial even when caught.
* REPAY keeps interest-first four/seven legs, no dedicated borrow decision,
  market dependency NONE, no new-borrow limit/quote requirement and no SELECT
  of current market/history in its financial isolation snapshot. Separate market
  metadata scope captures its own price baseline. Persisted isolation excludes
  writer lease/events and all auth tables; private raw starting rows never leave
  the actual process. Source acceptance equals inbox enqueue time, terminals
  cannot predate source, and borrow terminal cannot predate its actual decision.

The full-state snapshot is intentionally a correctness-first implementation,
not a high-throughput kernel. No performance, replication, HA, custody, lending
distress, insurance, ADL, HMAC origin or real-funds acceptance is claimed.

## Retained structural evidence and unexecuted gates

The first component window was 2026-11-17 14:39:19.714018–14:39:20.216030 UTC,
CPU4: nine tests, eight passed and one stale C1 test failed because it asserted
that newly implemented runtime APIs must still be absent. All22 actual effect
DDL definitions created against real core parent tables with clean FK catalog.
Source data/FK/COMMIT/reopen/unique-identity controls passed. These component
tests create no native owner, loan or successful permission callback.

The source fixture now explicitly uses `CATALOG_OBJECT_SQL`, the original raw
storage/FK/immutable model; it does not pretend full effect gates authorize raw
fixture writes. `OBJECT_SQL` is the complete48-object runtime catalog and is
always required by the real installer/loader. The stale assertion alone changed
to verify declaration-only fields without token/ready/permission; that one pure
case passed at14:40:25.201599–14:40:25.359941 UTC. The original8 green tests were
not rerun. The failed raw is retained. Afterward only the module introduction
was clarified; the manifest verifies its known tested source hash and identical
non-doc AST, without relabeling the original source/result.

Exact commands, hashes and outputs are retained under
`evidence/runs/credit-native-v2-runtime-candidate/`. The first actual publication,
owner, source/FIFO loan, dedicated replay, halt/stale-market repayment, restart,
savepoint/fault matrix and cross-runtime implementation tests are **pending**.
No structural pass substitutes for those native positive and negative gates.

## Deployment and rollback

This candidate ships no public activation command. Before publication a failure
rolls back the actual control transaction, including DDL. An existing identical
complete capability is verified without mutation; a different envelope refuses.
After any future successful publication, recover forward using original CIDs;
never delete a marker, downgrade format, reassign static claims or erase a
confirmed loan. Retain the exact code/runtime for replay. Independent financial,
native, failure and deployment reviews must pass before even this internal
scope can be called accepted; real funds require separate explicit approval.
