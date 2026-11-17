# Managed migration product scope review

Reviewed source: `af7abab42f421520496c7547abe88378b9db6cdc` on
`feat/uta-durable-integration`, reproduced in the independent
`test/migration-scope` worktree. This review changes tests and documentation only.
All accounts, amounts, markets, funding references, files, and requests are
synthetic. Production remains **NO-GO**. An agent's engineering review is not
financial launch approval.

## Conclusion and source-origin limitation

**No supported public `ShardRouter`-only spot-order origin was established.**
Its public order admission, cancellation, listing and matching operate on linear
orders. Calling its admission method with the configured spot symbol returns
`unsupported_product`; it does not create spot tables. There is no public spot
service accessor or spot component mount.

There is a reproducible compatibility-policy gap for an explicitly extended
source: a quiescent single-shard router layout can share its database and exact
catalog/rules with the public standalone `ExchangeService` and `SpotExchange`
classes. `take_over()` and even the fresh initializer's offline bootstrap accept
that source with live spot obligations and seal its financial writer. Managed
activation then succeeds, although the managed customer command protocol cannot
cancel or match those spot orders.

The standalone spot writes **bypass the router gate**. This is outside the routing
protocol guarantees stated in [sharding-capacity.md](sharding-capacity.md),
paragraph beginning “这套屏障要求所有写者使用 router” (source line 35).
The fixture therefore does **not** demonstrate an ordinary supported routed API
path or a vulnerability reachable through customer HTTP alone. Offline
quiescence and using public Python constructors do not remove that limitation.
It demonstrates that the migration boundary does not classify/reject that
persisted extension before accepting responsibility for it.

No source metadata, policy, identity, account routing or funding claim is forged.
All accounts, deposits, credit limits, funding pools, borrowing, interest and the
linear order originate through public `ShardRouter` methods. Only the spot
extension uses a separate public local `ExchangeService(Database(shard_path),
...)` with the **same** precision, fee policy, price age, catalog, portfolio rules
and audit policy. No `_services`, `_transaction`, SQL update, manually inserted
spot row or private source writer is used to create the source.

## Reproduced before and after

The configured source contains two accounts, USD/BTC cash and debt, principal
plus USD interest, genuine routed pool claims, and an accepted linear order.
The spot extension sells 2 BTC against a 1 BTC buy, then adds a separate 0.5 BTC
buy at USD 90. Both sides pay the configured `.0004` fee.

| Item | Before takeover | After completed takeover and actual managed activation |
| --- | --- | --- |
| Spot sell | `PARTIALLY_FILLED`, filled `-1`, remaining BTC lock `1` | Exact row retained; BTC lock remains `1` |
| Filled spot buy | `FILLED`, quantity `1`, no remaining lock | Exact row and trade/fills retained |
| Separate spot buy | `OPEN`, quantity `.5`, USD lock `45.018` | Exact row and USD lock retained |
| Ledger balances and liabilities | Settled BTC/USD transfers, fees, two asset debts and USD interest | Exact projection rows unchanged |
| Migration manifest and fence | No managed manifest/fence | `initialized=1`, financial authority `managed=true` |
| Global control | Legacy active source | Takeover first halts; explicit fresh market publication and managed activation return `halted=false` |
| Old standalone spot cancellation | Available before fencing | Rejected with `writer_fenced` |
| Managed spot order/cancel/match paths | No durable spot protocol | Actual authenticated loopback HTTP returns `501 unsupported_durable_operation` |
| Generic durable cancellation of spot ID | Spot ID belongs to the spot table | Queued normally, terminal `REJECTED/order_not_found` from the linear endpoint |
| Repay seller's remaining 1 BTC | BTC remains encumbered by the partial spot sell | Terminal `REJECTED/insufficient_cash`; lock and settled finances unchanged |

The runtime used real managed child processes, actual queue receipts, actual
fresh-market activation and the authenticated HTTP server. It did not manufacture
success receipts, alter command processing, or access a writer token. The test
observes existing shared lock accounting continuing to protect reserved assets;
it does not show double spending, lock release or lost settled funds.

The old authority cannot perform normal customer cancellation after fencing, and
the managed customer protocol lacks it. “Impossible to release forever” would be
an overstatement: the internal risk supervisor can cancel spot orders for a
distressed or non-normal account (`service.py`, source lines 1067–1075). That is
not a normal customer spot-cancel command. The reproduced healthy accounts keep
their locks during the exercised activation and rejection paths.

## Settled history is a distinct case

A second fixture cancels the partial sell and the open buy **on the old
authority**, retaining the already confirmed paired trade. Both accounts then
have no live spot locks. Takeover and activation preserve the complete spot
configuration, all three historical orders, the match receipt, both fills,
settled ledger balances and liabilities. Repayment of the released BTC succeeds
through the managed protocol.

The existing spot verifier succeeds before migration and on an independent
guarded read-only transaction after migration: `orders=3`, `matches=1`,
`paired_fills=2`. The latter uses the private `SpotExchange._verify(connection)`
audit hook solely to inspect the already committed rows, because the public
`verify()` wrapper opens a financial transaction and the old service is fenced.
It is disclosed as a private read-only diagnostic, **not** a migration check or
source writer path.

History surviving does not mean takeover reconciled it. The tests temporarily
replace `SpotExchange._verify` with a raising observer during takeover and
activation; both still complete. This observation does not change source state
or bypass any migration rejection.

## Actual verification coverage at the reviewed revision

| Boundary | Existing checks | Spot limitation |
| --- | --- | --- |
| Public router source | Linear product checks, funding registry, account hash and global gate | No public routed spot-order creation/matching |
| `initialize()` | Funding reconciliation, queue/config setup and irreversible fencing | No bootstrap product-obligation preflight or spot verification |
| `inspect_takeover()` | Layout, fence/queue status, ledger head, account/linear-order/position counts | Does not list spot tables, history, live statuses, reservations or schema |
| `take_over()` | Existing economic policy hash; service ledger validation; credit verification; exact global/local funding claims; account and queued-command routing | No `SpotExchange` construction or verifier call; prepares pending manifest and fences before these per-shard verifications |
| Managed activation | Halt receipts, funding claims, market digest/version and freshness | No spot compatibility or history reconciliation |
| Managed worker | Attaches credit and linear background worker | Does not attach `exchange.spot`; background spot matching requires that component |
| Shared repayment/risk accounting | Reads live spot reservations and subtracts them from available assets/collateral | Protects the lock but does not add customer cancellation capability |

Relevant source locations: `durable_process.py` lines 205–210, 433–440,
446–460, 483–550 and 1193–1211; `sharding.py` lines 408–417, 580–582 and
761–764; `spot.py` lines 396–472; `supervisor.py` lines 27 and 81–89.
The existing [spot deployment guidance](spot-settlement.md) requires spot,
credit and ledger reconciliation after startup/recovery and says that software
must not ignore remaining spot locks.

## Proposed policy for review; not implemented here

1. Define managed migration's admitted source products explicitly, including how
   unsupported direct extensions are identified. Treat inspection as a source
   inventory, not approval or a complete financial snapshot.
2. Under the exclusive offline control gate, inspect **all shards before any
   irreversible fencing or pending-manifest modification**. Reject unsupported
   live products with a stable, clear error. For spot, distinguish `OPEN` and
   `PARTIALLY_FILLED` obligations from terminal history and include any remaining
   asset reservation. Do not unlock or silently cancel them during migration.
3. Preserve the old source authority so the operator/customer can cancel or
   settle through its existing spot interface, then retry the same reviewed
   migration. A preflight rejection should leave manifest/fence, source orders,
   reservations, finances and original source write capability unchanged.
4. Admit terminal spot history only under an explicit preservation and
   reconciliation policy: verify schema/configuration, orders/fills, immutable
   match receipts, corresponding ledger/events and zero remaining obligations.
   Preserve settled assets, historical receipts and debt. Unknown or inconsistent
   extension state should receive a clear rejection before sealing.
5. Apply the compatibility rule to initializer bootstrap as well as takeover,
   and retain defense checks during activation/resume. Keep supported existing
   linear orders and mixed principal/interest liabilities working.

The review does not authorize a production patch. It does not recommend
classifying every catalog that lists a spot product as incompatible: an unused
catalog entry is not an in-flight obligation, and terminal settled spot history
does not require a live spot matching service.

## Reproduction and result

```sh
python -m unittest discover -s tests -p test_managed_migration_scope.py -v
```

Result on the reviewed source with this independent test file: **4 tests passed**
in approximately two seconds. Coverage includes the public-router-only linear
and mixed-liability control, extended live source takeover/activation/HTTP
behavior, terminal spot history preservation, and extended initializer bootstrap.

These are characterization tests of current acceptance, not assertions that
acceptance is the desired policy. A production fix must convert live-extension
acceptance into pre-fence rejection tests and keep the terminal-history and
supported-source controls. This small synthetic run supplies no production
capacity, financial policy, disaster recovery, real-funds or launch approval.
