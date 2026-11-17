# Independent managed migration reconciliation review

Reviewed commits: original characterization `0e049347`, implementation
`18e86b45b4331d622c4b896f540483e52ff29e68`. This independent change contains only
tests, documentation and raw observations. It does not repair damaged source
history, modify runtime, touch the frozen release or run a stability workload.

## Blocking result: settlement evidence is checked in one direction

`SpotExchange._verify()` starts with existing match receipts and confirms their
fills, journals and confirmation events. It never requires each retained
`SPOT_MATCH_CONFIRMED` / `SPOT_TRADE_CONFIRMED` event to resolve back to an existing
receipt. Consequently, deleting a complete business receipt bundle can remove
the very row that would have caused its corresponding evidence to be inspected.

The independent fixture first creates genuine synthetic routed cash/debt and
public standalone spot trades on the quiescent extended source described by the
implementation's scope document. The negative step is explicitly **offline
corruption**, not a supported router/customer path: remove paired fills, their
match and their order rows, then restore the exact original delete guards.
All settled ledger rows and original audit events remain unchanged. SQLite's
foreign-key check is empty; removing child rows before their parents does not
create a dangling SQL foreign key.

Two actual negative cases currently fail the required rejection assertions:

| Corruption | Actual verifier result | Actual migration result |
| --- | --- | --- |
| Remove the entire spot order/match/fill bundle; retain 8 original SPOT events and 8 ledger events | `matches=0, paired_fills=0, orders=0` | `initialized=1`, no error |
| Remove only the first complete trade bundle; retain a second valid trade, 13 original SPOT events and 9 ledger events | `matches=1, paired_fills=2, orders=3` | `initialized=1`, no error |

The second case rules out a defect limited to entirely empty spot tables.
Both cases assert that settled financial projections, original audit rows and
the damaged business rows remain unchanged during verification. Required behavior
is `503 spot_corrupt` from the verifier and takeover, before creating a managed
manifest, queue or fence. Inspection must reject and preserve; it must not
reconstruct the lost bundle, drop its remaining evidence or release money.

The standalone spot source itself is the explicit scope extension, outside the
router gate's ordinary writer guarantees. This is a migration financial-data
validation blocker under `LOCAL-MANAGED-MIG-001`, not evidence of a customer API
exploit or evidence that already confirmed settlement was reversed.

## Controls and current event contract

The independent single-leg control removes only one fill while keeping the
match, orders, audit and journals. Existing verification correctly returns
`503 spot_corrupt`; takeover stays unsealed and preserves the damaged state.
This passing control distinguishes the missing reverse check from a general
failure to inspect receipts.

Current successful spot execution emits these confirmation records in the same
financial transaction:

| Event | Outer account | Payload contract at the reviewed revision |
| --- | --- | --- |
| `SPOT_MATCH_CONFIRMED` | SQL NULL | Exact stored `uta_spot_matches` row: sequence, trade ID, symbol, base/quote, both account/order IDs, quantity, price, notional, both fees, journal event ID, market/catalog versions and creation time |
| `SPOT_TRADE_CONFIRMED` | The corresponding buyer or seller | `trade_id`, `symbol`, own `order_id`, signed `quantity`, `price`, own `fee`, `market_version`, `catalog_version` |

One execution has one global confirmation and two distinct customer confirmations.
The private quantity is positive for the buyer, negative for the seller; price
and fees remain decimal strings. The existing forward check compares the global
payload with the complete receipt and selected private fields with each side.
Reverse reconciliation must retain the account boundary and original fields; a
current quote is not a substitute for missing historical execution evidence.

Order lifecycle events are different. `SPOT_ORDER_ACCEPTED` contains the order
snapshot at admission; `SPOT_ORDER_CANCELLED` contains its cancellation snapshot
and `reason` (`customer_cancel`, an execution rejection or `risk_supervisor`).
They do not require a trade ID, match, paired fills or settlement journal. Earlier
snapshot status/version can legitimately differ from the final order row.

The independent positive control creates and cancels a never-filled order. Its
only SPOT events are `SPOT_ORDER_ACCEPTED` and `SPOT_ORDER_CANCELLED`; verification
and takeover must remain valid with zero matches. Do not classify every
`SPOT_ORDER_*` event as an orphan execution confirmation. This review specifies
the currently emitted kinds; it does not invent rules for future event versions.

## Other boundaries and scan cost

Four focused implementation cases passed independently: live spot on the last
shard leaves every earlier shard unfenced; preflight/verifier constructs no
financial service or writer transaction; and both initializer and takeover
post-preflight corruption leave the fence, incomplete manifest and HALTED gate.
Fresh no-spot initialization was separately observed as managed, inactive,
generation **0**. These checks do not establish a cross-shard rollback guarantee.

The verification adds unbounded work under lifecycle/control paths:

- With no spot table, presence detection uses `SELECT 1 FROM uta_events WHERE
  event_type GLOB 'SPOT_*' LIMIT 1`. The observed query plan is `SCAN uta_events`;
  the normal no-spot case must inspect the entire event history.
- Historical spot inspection performs full ledger verification and journal
  materialization, then loads audit events, matches and orders. For each match,
  the current Python implementation rescans the audit list twice: worst-case
  `O(matches * confirmation_events)`, quadratic when both grow together.
- The observed order-fill lookup plan is `SCAN uta_spot_fills` for
  `(account_id, order_id)`, adding `O(orders * fills)` work. By contrast,
  `trade_id` lookup uses the existing primary-key index.
- Preflight, token-owned final verification, constructor/worker readiness and
  activation repeat inspection. Activation holds the global exclusive gate.
  The scans have no row/page budget or cancellable verification deadline.

These are source/query-plan observations on tiny fixtures, not a capacity test.
The worker's post-inspection lease check remains necessary and correctly refuses
to announce an expired token ready; it does not make a large scan bounded or
guarantee operational startup/activation latency. This cost requires separate
review before claiming large-history availability. No heavy test was started.

## Reproduction and raw result

## Integration correction awaiting independent recheck

The integration now requires each global and private execution-confirmation
trade ID to resolve to an existing receipt, and each receipt to have exactly one
global confirmation and two distinct customer sides. The complete global row and
eight-field private payload use typed canonical JSON comparison, including the
historical market/catalog references; Python's `True == 1` is not accepted as a
version match. Malformed confirmation objects fail with `503 spot_corrupt`.
Unfilled/cancelled order lifecycle events remain outside the execution join.

The verifier builds audit, fill-by-trade and fill-by-order maps once per read
snapshot. This removes the repeated confirmation-list and per-order fill scans
described above, with additional in-memory fill indexes. Full ledger verification,
journal materialization and complete lifecycle scans remain; no large-history
latency, bounded-memory or capacity claim follows from this change.

The original four independent cases first reproduced two failures on integrated
`327d5fc` (1.200s). After correction, those cases, 15 migration cases, 19 spot cases
and seven typed/customer-side corruption cases passed: **45 tests, 9.603s** on
Python 3.12.14 / SQLite 3.53.1. Raw integration red/green evidence is retained in
`evidence/runs/migration-reverse-audit/`. These are targeted results; independent
recheck, final source freezing, full-suite/package checks and the managed long run
are still required. Historical red artifacts above remain unchanged.

Deployment uses a new fixed artifact in a separate synthetic authority, or stops
writers before inspecting an existing source. Rejected history stays unsealed
and HALTED with its original records; resolve corruption through a separately
reviewed source-recovery process. This correction creates no tables or financial
entries and does not recover lost receipts. Roll back code only while preserving
authority state and the source gate; an older verifier's acceptance cannot be
used to override the new corruption rejection or enable real funds.

```sh
/usr/bin/python3.13 -m unittest tests.test_migration_reverse_evidence -v
```

At the reviewed runtime this runs four cases in **1.334 seconds**, with the two
missing-bundle cases failing and the single-fill/order-lifecycle controls passing.
The failures are retained as ordinary failures, with no skip/expected-failure
annotation or softened assertion. The additional four lifecycle/scope checks
passed in **1.095 seconds**. See the [raw red result](../evidence/runs/migration-reverse-audit/red-py313.txt),
[scope controls](../evidence/runs/migration-reverse-audit/scope-controls-py313.txt)
and [digest manifest](../evidence/runs/migration-reverse-audit/manifest.json).

Runtime repair and rerunning these same assertions are outstanding. This review
does not approve migration or production use and cannot qualify a long run.
