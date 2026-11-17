# Managed migration product scope and compatibility policy

Rule version: **LOCAL-MANAGED-MIG-001**. Production remains **NO-GO**. An agent's
engineering review is not financial launch approval. All reproduced accounts,
amounts, markets, funding references, files and HTTP requests are synthetic.

## Current policy

The managed runtime accepts linear order/cancellation and explicit repayment
commands. It has no managed spot order, spot cancellation or spot matching
protocol. Listing a spot product in the catalog does not activate those commands
and does not by itself make a source incompatible.

Before creating a pending managed manifest, a queue or any irreversible shard
fence, initializer/bootstrap sealing and explicit takeover inspect **all shards**
under the exclusive offline router gate:

| Source state | Result |
| --- | --- |
| No spot state or spot audit history | Existing linear and mixed principal/interest behavior continues |
| `OPEN` or `PARTIALLY_FILLED` spot order, even with zero reservation | `409 managed_spot_state_unsupported` |
| Any finite positive remaining spot reservation, including a terminal order | `409 managed_spot_state_unsupported`; reservation is retained |
| Complete `FILLED`/`CANCELLED` spot history, zero remaining obligations | Verify existing schema/configuration, receipts, paired fills, journals, events, order aggregates and locks, then preserve all history and settled assets |
| Missing/unknown spot schema, configuration mismatch, missing receipt guard, malformed amount, negative reservation, inconsistent receipt or orphaned spot audit history | Reject with `spot_corrupt` or `spot_schema_version` (503); never create missing objects as a repair |

The compatibility check uses `SpotExchange(..., initialize=False)` and its
existing independent verifier. Parent preflight creates narrowly scoped
`ExchangeService` and `DurableLedger` verification views with `__new__`; neither
financial constructor runs. The views only issue read queries in the caller's
guarded snapshot and do not escape the helper. Parent preflight uses a read
transaction. `SpotExchange.verify(connection=...)`
can join that snapshot; `verify()` also opens a guarded read transaction.
Initialization disabled means **no DDL, schema installation, trigger installation,
or implicit configuration repair**. A legacy-reference source without an account
product catalog still loads and checks the persisted standalone spot catalog and
fee policy; it cannot silently drop that history.

After fencing, token-owned final verification checks the actual persisted spot
state before the manifest can be marked complete. The fresh initializer retains
its existing generation-zero behavior when a post-fence read confirms there is
no spot footprint; an old writer cannot add one after that fence. Any existing
spot footprint takes the token-owned verification path. A quiescence violation
that adds live state after preflight is caught after fencing and leaves the
manifest incomplete. Reopening, worker readiness and activation also check spot
compatibility. Worker readiness rechecks/renews the same still-live token after
historical verification; an expired token cannot be revived or advertised READY.

These checks do not attach a spot trading component to a managed worker. Actual
authenticated spot order/cancel/match HTTP paths continue to return
`501 unsupported_durable_operation`.

## Source-origin limitation remains explicit

No supported public `ShardRouter`-only spot-order origin was established. Its
public order admission, cancellation, listing and matching operate on linear
orders. Passing the configured spot symbol to routed admission returns
`unsupported_product`; there is no public spot service accessor or mount.

The positive spot fixtures use a quiescent, single-shard layout with genuine
public routed accounts, deposits, credit limits, funding pools, loans, interest
and a linear order. A separate public standalone
`ExchangeService(Database(shard_path), ...)` plus `SpotExchange` uses the **same**
precision, fees, price age, catalog, portfolio and audit policy. No private source
writer, fabricated claim, identity change or policy rewrite creates that state.

Those standalone spot writes **bypass the router gate** and remain outside the
routing protocol guarantees stated in [sharding-capacity.md](sharding-capacity.md)
(source line 35 at the reviewed revision). Offline quiescence and public Python
constructors do not turn them into an ordinary supported routed API path. This
change defines how managed sealing rejects or reconciles such persisted source
extensions; it is not evidence of a customer HTTP exploit.

Negative tests deliberately damage synthetic terminal records/schema or inject a
writer between preflight and fencing. Those fault injections are explicitly
identified and are not presented as ordinary source operations.

## Recovery and preservation

1. On a **pre-seal** `managed_spot_state_unsupported` rejection, the global router
   gate is HALTED. No pending managed manifest, queue or shard fence was created.
   Accepted financial rows, settled assets, liabilities, spot orders and their
   reservations are retained. Operational halting may append its own
   `KILL_SWITCH_CHANGED` audit event; it never overwrites existing events.
2. Cancel or settle the live spot obligation on the original standalone source
   authority. The migration does not cancel orders, release locks, manufacture a
   fill or drop historical tables. Existing cancellation remains usable while
   halted. Reconcile the source, maintain offline quiescence, inspect the layout
   again, then explicitly retry `take_over(managed=True, expected_layout_hash=...)`.
3. A rejected fresh initializer does **not** roll back already committed bootstrap
   work across shards. It retains that unsealed source and halts it. After old
   authority cancellation/settlement, use explicit takeover of the existing
   layout. Retrying fresh `initialize()` on a nonempty directory is not recovery.
4. If a trusted direct writer violates quiescence **after preflight**, the final
   token-owned check can reject after an irreversible fence exists. The pending
   manifest remains `initialized=0`, the global gate remains HALTED, and normal
   reopening refuses incomplete bootstrap. Preserve the error and audit evidence
   and perform reviewed forward recovery on that authority. Do not disable the
   fence, restore an older financial snapshot, delete obligations, or claim that
   an old standalone service can resume writing after fencing.
5. For corrupt history, preserve evidence and reconcile/repair through an
   explicitly reviewed source or forward-recovery procedure. Inspection never
   fills missing tables/guards or treats missing history as zero. A schema/config
   error is not an instruction to recreate it with the normal constructor.

The internal risk supervisor can cancel spot orders on distressed/non-normal
accounts. That does not provide the missing managed customer cancellation
protocol and is not a reason to allow unsupported live obligations through
migration. The policy does not classify a reservation as lost or releasable just
because the new runtime cannot service its product.

## Historical reproduction and immutable origin

Reviewed runtime origin: `af7abab42f421520496c7547abe88378b9db6cdc`.
Independent original evidence commit:
`0e04934710292a9804dea577c34713c3453a626b` (`test/migration-scope`). Its original
four characterization tests and full report are available unchanged with:

```sh
git show 0e04934710292a9804dea577c34713c3453a626b:tests/test_managed_migration_scope.py
git show 0e04934710292a9804dea577c34713c3453a626b:docs/managed-migration-scope-review.md
```

At that origin, the extended source sold 2 BTC against a 1 BTC buy, then added a
0.5 BTC buy at USD 90. With the `.0004` fee, it retained a partially filled sell
with a BTC 1 lock and an open buy with a USD 45.018 lock. Original takeover and
fresh bootstrap both sealed that source. Actual managed processes published a
fresh market and activated with `halted=false`. The old spot cancellation then
returned `writer_fenced`; HTTP spot commands returned 501; generic cancellation
of the spot ID returned terminal `REJECTED/order_not_found`; repayment of the
locked BTC returned `REJECTED/insufficient_cash`. Locks, settled balances, debt
and spot history remained intact. The original migration did not invoke the
existing spot verifier. This is the conditional compatibility gap addressed by
the current policy, with the source-origin limitation above.

The separate terminal-history fixture cancelled the old live orders, retained
one confirmed trade and two fills, then migrated without losing settled assets
or historical rows. The new implementation preserves that behavior and now
actually verifies the history before sealing.

## Verification

```sh
python -m unittest discover -s tests -p test_managed_migration_scope.py -v
python -m unittest discover -s tests -p test_spot.py -v
python -m unittest discover -s tests -p test_durable_process.py -v
```

The migration suite checks pre-seal rejection with unchanged financial rows and
locks; live state on the last shard leaving all earlier shards unfenced;
bootstrap facts retained unsealed/HALTED; verified terminal history preservation
and activation; no financial constructor/write transaction during preflight;
legacy standalone catalogs; incomplete/malformed schema, policy, guards and
receipt failures without repair; token-owned rejection of post-preflight live
state or damaged terminal history; and unchanged supported linear/mixed-debt
behavior. The original acceptance assertions are retained only in the immutable
evidence commit; current tests require rejection at the new policy boundary.

These bounded synthetic tests do not establish production capacity, financial
policy approval, external custody, real-funds safety, disaster recovery or launch
readiness. Production remains **NO-GO**.

Recorded bounded regression result for this policy implementation: migration
scope **15 passed**, standalone spot **19 passed**, durable process **17 passed**,
and durable CLI **7 passed** (58 tests total). `git diff --check` also passed.
