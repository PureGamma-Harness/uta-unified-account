# Closed-by-default native credit financial hooks

The existing `_borrow` calculation, original CID replay, gross liability rules,
LTV/step/limit/pool checks, late margin check and caller rollback contract remain
the financial implementation. A managed new borrow now has an additional
format2-only branch requiring the actual same-connection native operation scope
and complete dedicated capture before effects. The complete borrow decision is
inserted after actual version/receipt construction and before the original
credit receipt is closed. The native deferred obligations and financial COMMIT
verifier must then close all actual rows. A missing operation scope retains the
public `unsupported_credit_operation`501 rejection. A corrupt or poisoned
context is not downgraded to that ordinary unsupported response.

Pre-cap and first PREPARED capabilities remain unchanged. Replay of an original
credit CID precedes capability, halt, price and fresh-admission checks and does
not create a new audit or source. Public borrowing never creates a native scope.
Existing non-cap repayment is unchanged. This hook does not open a route or CLI.

The full loaded-code artifact now covers dedicated capture/replay, native V2,
FIFO, transition, wire contract and the actual existing-service factory. The
factory accepts V2 auxiliary constraints only from the two exact compiled
native/audit inventories after actual `_load` validation, preserving the core
financial CREATE definitions. It does not accept a namespace prefix as proof.

The recorded 17-case run in `evidence/runs/credit-v2-borrow-hooks/first` passed
the actual original joined-borrow/SAVEPOINT/managed501/replay cases and extended
artifact generation. It is regression/component evidence, not successful V2
execution. Positive full native installation, durable borrowing, independent
operation oracle, reopen/restart and lost response checks remain required.
Deployment stays closed with no new setup command. Binary rollback is allowed
before a V2 authority exists; after publication only the exact compatible
artifact and complete native loader may own it. Never remove markers or rewrite
financial history to roll back. Real-funds and external HMAC borrowing remain
disabled pending their separate acceptance and approval.

The first internal V2 account is deliberately a restricted synthetic authority:

| Operation after V2 publication | Current internal boundary |
| --- | --- |
| Explicit BTC BORROW | Original trusted synthetic source, account FIFO, full native context and complete dedicated evidence are mandatory |
| BTC REPAY | Original source/FIFO and native four/seven-leg obligations; market dependency NONE |
| Internal halt or market publication | Separate actual native metadata scope and exact permitted deltas |
| Original pre-cap credit CID | Read-only original result; no historical source/decision reconstruction |
| Generic writer/normal worker READY/CLI activation | Unsupported; no automatic promotion to V2 |
| New orders, matching fills, spot operations, withdrawals or mode changes | No V2 transaction adapter in this first slice; financial guards fail closed without effects |
| New pool funding, interest accrual or lending distress/insurance/ADL | Unsupported after publication; native SQL guards fail closed without effects |

Opening orders/positions/debt may be valued if their exact supported original
rows pass full verification, but that is not permission for new execution of
those operations under V2. This restriction must not be presented as a
production trading account or used to migrate real customer accounts.

`ExchangeService.readiness()` additionally reads the actual persisted native
format and returns `ready:false` with reason
`internal_credit_authority_not_trading` for format2. A real internal financial
lease therefore cannot be misreported as generic trading readiness. The no-cap
ready/halt result was separately checked on an actual temporary database in
`evidence/runs/credit-v2-readiness-boundary`; the actual format2 branch remains
part of the full native positive-chain acceptance, not that default-path test.
