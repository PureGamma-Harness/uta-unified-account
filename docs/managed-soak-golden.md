# Managed soak golden workload

This is the synthetic workload contract for a new managed process soak based on
`4c68f01`. It is separate from `benchmarks/run_soak.py` and the already running
887/observer evidence. A result from that earlier source cannot qualify this
managed candidate. The first implementation runs only 10-second and 60-second
smoke cases. A 6-hour or 24-hour job needs a separately frozen source manifest,
configuration and reviewed start; this document does not start or approve it.

## Authority, transport, and fixed budget

Use one stable managed directory, the same account identities, and the original
business IDs throughout a job and every resume. The concrete runtime class is
`uta.durable_process.DurableProcessRouter`; it spawns actual fenced worker PIDs.
Required audit/schema 3 is mandatory (`decision_audit=True`). Default execution
caches remain disabled. Record configured shard count and the chosen trading
shard; all three test accounts must belong to that shard because matching is
local to a shard. This workload proves neither cross-shard settlement nor HA.

A separate initialization process performs the explicitly authorized offline
bootstrap before `initialize(..., managed=True, bootstrap=...)` seals the
financial authorities. The CLI `init` alone creates no accounts or funding.
Bootstrap creates two traders, Alice and Bob, and one credit account; records the
actual stable names and shard; deposits 1,000,000 USD to each; and deposits a
1 BTC repayment buffer to the credit account. Scales are USD=8 and BTC=8.

Use the synthetic catalog/rules defined by `uta.examples.synthetic_policy` and
fee rate 0.0004. The trading instrument is BTC-PERP: linear USD settlement,
multiplier 1, quantity step 0.01, price tick 0.01, minimum notional 1 USD.
Execution prices are always 100 USD, and every fresh synthetic mark/index input
is 100. Prices remain synthetic, not a calibrated real-market feed.

Let `N = floor(duration_seconds * 0.25)` be the immutable planned round budget,
and let one BTC minor unit be `u = 0.00000001 BTC`. Configure and fund explicit
BTC pool/account limits. Fund the synthetic pool with `F=1 BTC`, then create a
real bootstrap loan with principal `P0 = 2*N*u`, zero interest, and a unique
source reference. Record its actual credit command and journal IDs. Bootstrap
must have enough cash, principal and pool capacity for the whole selected job;
there is no recurring privileged borrow, deposit or interest accrual during it.
At 24 hours, N=21,600 and P0=0.000432 BTC. The 1 BTC buffer is ample.

After sealing, every financial change goes through the legitimate token-bound
worker. The controller may write its separate checkpoint database, authentication
store, and supported router control metadata. It must not construct an unbound
ExchangeService/Matcher/CreditService to write managed financial state, repair
schema, fabricate a fill, or top up the accounts after restart.

Start the actual `python -m uta.durable_cli serve` command with its default
`hmac-tls` profile. Generate private synthetic certificate/key/signing material
at runtime outside Git, bound to loopback with IP SAN 127.0.0.1. Client TLS uses
`ssl.create_default_context(cafile=certificate)`, CERT_REQUIRED and hostname/IP
checking. Do not use an unverified context or a development-profile fallback.
Use trader keys scoped to each trader and a funding key scoped to the credit
account; an admin/operator key may query health. `sign_headers` is a permitted
transport helper, not a financial oracle. Each HTTP attempt uses a new nonce and
signature while preserving its original business command ID.

## One deterministic round

Round r is one-based, planned at `job_start + (r-1)*4 seconds`. Admit at most one
active round: a slow or unknown round stops progression; it never creates a
catch-up burst. The 0.25 round/s budget includes six command submissions, their
queries, two actual matches, market publication, activation and verification.
It is not a claim of 0.25 HTTP requests/s or of exchange capacity.

| Step | Action | Required durable fact before the next step |
| --- | --- | --- |
| feed | Publish a new actual-UTC snapshot, then activate | All shard publication/activation receipts committed and barrier open |
| open-buy | Alice buys 0.02 BTC-PERP at 100 | Original admission CID is SUCCEEDED |
| open-sell | Bob sells 0.01 at 100 | Original admission CID is SUCCEEDED |
| open-match | Wait for the real worker matcher | Exactly one paired match for these orders, quantity 0.01 at 100, two committed fills |
| cancel-partial | Cancel Alice's remaining 0.01 | Cancel CID SUCCEEDED; original buy has filled=0.01 and terminal CANCELLED |
| close-sell | Alice sells 0.01 at 100, reduce-only | Original admission CID is SUCCEEDED |
| close-buy | Bob buys 0.01 at 100, reduce-only | Original admission CID is SUCCEEDED |
| close-match | Wait for real worker matching | Exactly one additional paired match, quantity 0.01 at 100; both positions flat |
| repay | Credit account repays 0.00000002 BTC | Repay CID SUCCEEDED with principal_repaid=0.00000002 and interest_repaid=0 |
| verify | Read one consistent financial snapshot | All golden balances, joins, audit links and uniqueness checks pass |

Cancellation must precede the close orders. Otherwise the old resting buy can
interact with a close order and exercise self-trade prevention rather than the
intended paired close. Matching is observed, never invoked through a bare parent
Matcher. Market price is not used as an invented executable price.

There are six client commands per round: four admissions, one cancellation and
one repayment. Two matching confirmations are separate worker effects. Stored
admission receipts are immutable and may still say OPEN/filled=0 after later
fills; query the actual read-only order/fill/match state for partial-fill proof.
The final order states are CANCELLED for Alice's original buy and FILLED for the
other three orders. No live order or position remains at the round boundary.

## Independent arithmetic oracle

Implement these checks with integer minor units or independent rational
arithmetic. Do not call the production reserve, PnL, fee, credit, or portfolio
calculation helpers to produce expected values. With q=0.01 and price=100, one
fill side has notional 1 USD and fee `1 * 0.0004 = 0.0004 USD = 40,000` USD minor
units. Each trader executes two sides, so every completed round costs each
80,000 minor units. Both entry and exit execute at the same price, hence realized
PnL is zero. All quantities and fees are exactly representable; no rounding edge
is hidden in this golden case.

After r fully verified rounds, with initial balances A0=B0=1,000,000 USD:

- Alice USD minor units: `A0*10^8 - 80,000*r`; Bob has the same formula.
- `system:fees` USD increase: `160,000*r` minor units.
- Both trader positions and remaining order reserves: zero.
- Matching: `2*r` distinct trade IDs, `4*r` distinct fills, `4*r` orders, exactly
  `r` partly filled orders cancelled, and no unmatched execution side.
- Credit BTC cash minor units: `100,000,000 + 2*N - 2*r`.
- Credit principal minor units: `2*(N-r)`; interest: zero.
- Pool BTC cash minor units: `F*10^8 - 2*N + 2*r`; principal receivable equals
  `2*(N-r)`. At the final round the pool is restored to F and the customer retains
  its original 1 BTC buffer with no debt.
- Every currency's complete journal posting sum is zero. Cash/debt/receivable
  components remain separate; do not infer conservation by netting gross debt.

Before cancellation, Alice's partial position is +0.01 with signed cost basis
+1 USD; Bob is -0.01 with cost basis -1 USD. The first fill fee is 40,000 USD
minor units per account. This gives a small manually inspectable intermediate
case as well as the flat end-state. Each new round must match exactly its own
order IDs; global counts alone cannot prove correct pairing.

## Command IDs and crash boundaries

Choose a random job identifier once and persist it before initialization. Use
bounded ASCII IDs such as `ms:<job12>:r000000001:open-buy` for CIDs and
`ms:<job12>:r000000001:o:open-buy` for order IDs. Include account, method, target,
canonical exact payload bytes and a digest in the checkpoint before sending.
Never regenerate a job identifier or replace an unknown CID during resume.

A separate SQLite checkpoint database may hold INTENT, ENQUEUED, TERMINAL,
FINANCIAL_PROOF and VERIFIED facts plus append-only evidence/export cursors. It
has no cross-database atomic transaction with the financial authority. Recovery
always reconciles the finance side first:

1. For a persisted INTENT or ambiguous HTTP outcome, GET the original account/CID
   with a fresh request nonce. A scoped 404 permits resubmitting exactly that
   original CID and payload. A missing local checkpoint never proves no effect.
2. PENDING is only durable enqueue. Keep querying without declaring risk
   acceptance. A timeout/connection loss is UNKNOWN, never a business rejection.
3. SUCCEEDED is the committed command receipt; independently verify the required
   match/order/debt facts before advancing the local checkpoint. A crash after
   finance COMMIT but before checkpoint COMMIT therefore queries, rather than
   repeats business under a replacement ID.
4. REJECTED or QUARANTINED is retained as a real terminal outcome and stops this
   success-golden stream. It is reported separately; no new CID repairs the score.
5. Recover the earliest unresolved step and round first. Never move to r+1 until
   all r effects are known and the independent oracle has verified the boundary.

Use real periodic SIGKILL of an identified worker and real parent-process
termination/restart. Retain PID/start-time/generation before signaling, verify
identity to avoid PID reuse, and retain the replacement PID/generation. Killing
just after a POST intentionally allows either side of COMMIT; do not assert that
timing proves rollback. Parent recovery uses the existing source/configuration,
auth DB and original financial files. It must neither reinitialize a nonempty
managed directory nor erase consumed nonces.

## Feed, evidence, and acceptance limits

Managed publication deliberately halts the global barrier. Serialize fresh
publication/activation with the command pipeline instead of racing a background
feed against queued submissions. Publish before each round with a strictly
increasing version and its actual observation time. Retrying an in-flight
publication preserves its exact snapshot bytes and timestamp; a new snapshot is
not a retry. HTTP router control publication is explicitly unsupported, so use
the real operator CLI `publish`/`activate` against the active coordinator.

With a four-second round schedule, max price age 30 seconds and bounded recovery
below ten seconds, quotes remain genuinely fresh in the intended smoke path.
Record actual publication gaps, not assumed gaps. If a long outage makes a
pending admission legitimately reject on stale data, preserve that result and
stop the golden stream. Do not re-sign a fabricated timestamp or silently start
a new command. Include CLI/feed/recovery/checkpoint waits in scheduled-arrival
latency. Report delayed rounds, actual wall/active time, queue age and drain time.

Required audit must remain required after parent restarts. Each round contributes
four ORDER_ACCEPTED and four FILL_CONFIRMED decisions with real market, policy
and artifact links, assuming an otherwise empty isolated trading fixture. Check
full market payloads, artifact/policy hashes and each order/fill link. Existing
archive replay can be an additional check but is not the independent cash oracle.
The current audit capability explicitly does not archive risk-reducing cancels,
repayments or new credit decisions as risk decisions; their command, credit and
journal receipts remain required evidence, and this gap must be reported.

Keep the existing soak architecture's immutable source/environment manifest,
private locked job directory, append-only event stream, bounded segmented exports,
fsync+atomic metadata replacement, disk/free-space bounds, session accounting,
heartbeats and read-only final reopening. Do not modify the earlier soak source
or attach to its PID/authority. Each new managed run has a distinct directory and
source manifest. Defaults remain `production_approved=false` and
`twenty_four_hour_pass=false`. Only a final independent audit of the actual
completed duration, original commands and full evidence may assess a duration
gate; elapsed wall time or a successful smoke never flips a production flag.

This stream covers configured linear perpetual admission, real paired partial
execution/cancel, reduction, existing-debt repayment, required linear audit,
TLS/HMAC ingress and single-host process recovery. It does not cover runtime
borrow/interest accrual, liquidation/insurance/ADL, spot execution, PM/options,
multiple settlement currencies, cross-shard matching, capital calibration,
replicated commits, disk/AZ loss, external custody or 10,000/s capacity. Low-rate
soak counts and latency must be labeled separately from independent open-loop
throughput diagnostics and from the earlier 887 experiment.
