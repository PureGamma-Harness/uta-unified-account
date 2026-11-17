# Managed v2 read projections

This extension adds account-scoped REST reads to the durable v2 server. Command submission/status semantics are unchanged: `202 durably_queued` remains a producer ACK, and financial execution still belongs to the fenced writer. This branch does not approve G7, production capacity, financial rules, or WebSocket delivery.

The parent reader opens an **existing** private authority with `Database.read_transaction()`. It never constructs `ExchangeService` or `DurableLedger`, installs a schema, creates a missing financial database, repairs audit guards, acquires a writer token, or changes balances. All metadata and requested rows in one response come from the same SQLite WAL snapshot.

## Routes and authorization

All routes below use existing HMAC/Bearer profile authentication and account scope. Reader/trader may read only their bound account; risk/admin may select an account. Funding retains its limited repayment/command permissions and receives 403 for these new financial projections. Role/scope checks precede the view query. Unknown accounts/resources do not trigger construction or migration.

| GET route | Contents |
| --- | --- |
| `/v2/accounts/{aid}` | Settled asset balances, separate principal/interest, position/order counts |
| `/v2/accounts/{aid}/orders` | Paged linear order projection, including terminal orders and audit links |
| `/v2/accounts/{aid}/orders/{oid}` | Current stored projection of one original order ID |
| `/v2/accounts/{aid}/positions` | Paged signed base quantities and signed USD cost basis |
| `/v2/accounts/{aid}/ledger` | Paged statement containing only this customer's postings |
| `/v2/accounts/{aid}/events` | Paged private account events, filtered before applying the limit |
| `/v2/accounts/{aid}/liquidation` | Stored supervisor state or explicit `not_evaluated` |
| `/v2/accounts/{aid}/decisions/{did}` | Owned historical decision, inputs, summaries and referenced archives |

`/v2/accounts/{aid}/risk` remains 501. Live risk/reserve recalculation is not enabled here. Read support must not be used as permission to bypass the current market/policy checks of financial admission.

The existing `/v2/accounts/{aid}/commands/{cid}`, orders/cancel/repay commands, control protocol and worker diagnostics keep their previous responses and permission rules. There is no global customer-data listing endpoint. For a process router, the account selects its owning shard; this API does not combine an account across shards or claim an atomic multi-shard snapshot.

## Snapshot envelope

Each successful response contains `snapshot`, alongside the requested resource:

```json
{
  "snapshot": {
    "account_id": "alice",
    "account_version": 12,
    "authority_id": "managed-authority-id",
    "shard": 0,
    "stream_id": "account-stream:<sha256>",
    "trading_schema": 3,
    "market_snapshot_id": "market:<recorded-payload-sha256>",
    "market": {
      "freshness": "stale",
      "version": 4,
      "observed_at": "2026-11-16T00:00:00+00:00",
      "payload_digest": "<sha256>",
      "evidence": "recorded"
    },
    "policy_ref": {
      "kind": "persisted_financial_config",
      "id": "config:<sha256>",
      "risk_mode": "phase1_cross",
      "archived_policy_id": null
    },
    "events_watermark": 400,
    "account_events_watermark": 397,
    "ledger_watermark": 80,
    "checked_at": "2026-11-16T00:00:10+00:00",
    "reporting_currency": "USD",
    "local_halt_observed": false,
    "risk": {"status": "unsupported", "reason": "live_risk_recomputation_not_enabled"}
  }
}
```

The account version, current market archive ID, persisted financial policy reference and watermarks are selected in the **same read transaction** as the response data. A writer may commit concurrently, but its later version/balance/market cannot be spliced into that response. This is a snapshot at the reader, not a guarantee that the account remains unchanged after delivery.

`policy_ref.id` is a content reference to the authority's persisted financial `policy` plus `risk_policy` config. It is deliberately distinguished from an archived decision's `policy_id`: the current active archive pointer is not persisted as a unique singleton, and equivalent financial policy may have multiple execution-option artifacts. The reader does not invent an active archived ID from the latest decision.

For schema 3, the current market ID must resolve to the exact recorded bytes, and the existing audit capability/guard inventory is validated without repair. Missing or inconsistent required evidence fails with 503. Schema 2 remains readable, with `market_snapshot_id: null` and `market.evidence: legacy_unarchived`; no market history or decisions are backfilled by a read. Its decision endpoint returns 501.

Market freshness is `fresh_as_of_read`, `stale`, `future`, or `missing`, using the persisted max-age policy and current reader clock. `fresh_as_of_read` does not mean the account passed risk checks. `local_halt_observed` is the local SQL flag, not a global router activation/readiness conclusion. Worker liveness/control diagnostics are also not an account trading decision.

## Units and explicit gaps

Balances are exact decimal strings with the configured asset scale and `unit: asset_units`. They are settled balances, may be negative, and are not USD equity, net collateral, spendable cash, or a reconstructed loan value. Principal and interest are separate asset-unit strings; they are not netted against assets.

Stored monetary strings must use ASCII decimal syntax; whitespace, underscores, Unicode digits and nonfinite values fail with `503 view_data_invalid`. Principal and interest must be nonnegative, exactly representable in their asset's minor units, and within the existing credit/ledger bounds (at most 38 coefficient digits, exponent -38..38, each value below `10^38` minor units). Scientific notation and redundant fractional zeros remain valid when they represent exact minor units, for example `1.0E-8` at scale 8. The reader preserves valid stored strings and validates these bounds using exact tuple/integer conversion, without rounding or relying on the ambient Decimal context. These checks do not reconcile gross debt against all ledger postings; reconciliation remains an operator responsibility.

Positions contain signed `quantity` in `base_units` and signed `cost_basis` in USD for the supported linear contract. The reader does not round a derived average entry price or compute PnL. Orders return `reserved_margin: null` and `reserve_status: not_recomputed`; account `encumbrances.status` is likewise `not_recomputed`. Null/unsupported must not be interpreted as zero reserve or permission to withdraw/trade.

Liquidation reads return the stored supervisor row and `meaning: stored_supervisor_state_not_live_risk_assessment`. A missing row is `not_evaluated` with no fabricated NORMAL state. A stored NORMAL row is not a fresh risk assessment, and a BANKRUPT row is not proof of insurance/ADL completion.

The ledger endpoint is a **customer statement projection**, not a complete double-entry journal. It exposes only the requested customer's asset postings, exact minor-unit amounts/scales, and event hash/ID references. It does not expose other customers or system contra accounts. A full journal verification requires the separate operator reconciliation path; this projection cannot prove per-event global balance by itself.

Decision evidence is selected with both decision ID and account ID. Historical before/after versions, summary, market bytes and policy/artifact content IDs are validated in the same read snapshot. The historical market/policy under `decision` can differ from the current market/config under `snapshot`; that is expected. The response labels this as content/version verification, not replay approval, current financial safety, signed release attestation, or renewed execution authorization. It does not instantiate the audit/replay engine. Legacy decisions and unsupported kinds are not fabricated.

## Paging, gaps and reconstruction

Orders, positions, ledger and events accept:

| Query | Meaning |
| --- | --- |
| `after` | Exclusive nonnegative integer cursor; default 0 |
| `until` | Inclusive upper watermark; default current resource watermark |
| `limit` | 1..200, default 100 |
| `stream_id` | Optional expected account stream identity; recommended on every resume |
| `at_version` | Optional exact account version for an unchanged account projection |

Account, single order, liquidation and decision reads accept only `stream_id` and `at_version`. Duplicate, unknown, malformed or unsupported query fields are rejected rather than ignored.

Each paged response has `page: {after, until, limit, has_more, next_after}`. Save `until` from the first page when draining a bounded range. If more scoped rows remain, `next_after` is the last returned cursor. At the end of that range it advances to `until`, including when no private row exists in a global sequence gap. Repeating the same range may return the same immutable events; apply/deduplicate by `(stream_id, sequence)` and persist the cursor only after applying a page.

Event cursors are global **within the shard**, while the SQL predicate limits payloads to the account before LIMIT. Gaps from other accounts or global market/control events are normal; they are not proof of loss. This private stream does not contain global price/control updates. Ledger cursors use their own journal sequence, independent of event sequence. An event ID or timestamp is not a substitute for these cursors.

Order/position cursors are stored row IDs for paging the current projection, not immutable change-stream offsets. Fills/cancels can update old order rows; positions can be replaced. Use `at_version` to detect account changes across pages and restart snapshot reconstruction on a 409. Each HTTP response has its own read transaction; the server does not hold a database snapshot open across requests. Also compare returned market/config references if assembling data with a market basis, because market publication need not change the account version.

`view_version_changed` means the account changed during reconstruction. `view_stream_changed` means authority/file/account stream identity changed: discard the old cursor and rebuild. `view_cursor_ahead` means the requested cursor/watermark exceeds current stored history; do not silently reset to zero or assume the missing range was delivered. Stream identity includes authority, canonical local file identity and account, and therefore changes on an ordinary replacement/restoration file. It is not an external anti-rollback seal against a trusted OS owner restoring bytes in place or cloning the whole machine.

For later private WebSocket work, REST currently provides only snapshot watermarks and an immutable private-event pull contract. It does **not** implement subscriptions, acknowledgement storage, backpressure delivery, reconnection orchestration or exactly-once network delivery.

## Failure and validation

Bad query fields return 400. Missing account/order/owned decision returns 404. Cursor/stream/version rebuild conditions return 409. Unsupported risk/schema/capability returns 501. Missing database, corrupt monetary data, required tables/guards/archive links, unavailable reader clock or inconsistent authority returns 503. These failures do not create schema, repair data, write financial state or reroute to a synchronous writer.

Tests in `test_durable_views.py` exercise actual HTTP and HMAC account scope, permissions checked before view access, exact asset/minor-unit conversion under hostile Decimal context, concurrent WAL writer commits between metadata and row reads, event gaps/pagination/dedup, customer-only ledger postings, version/file replacement rebuilds, historical versus current market refs, stale/future/unevaluated states, legacy gaps, missing-data refusal, original command-query compatibility and correct existing-router shard selection without financial constructors. Existing durable command and signature suites are also run. This remains synthetic local validation pending independent review and production signoff.
