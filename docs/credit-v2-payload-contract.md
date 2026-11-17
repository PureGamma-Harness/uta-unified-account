# Dedicated credit V2 canonical payload contract

The normative field sets are published in `uta/credit_v2_payload_contract.py`.
They describe retained data, not a capability or evidence that capture has run.
This contract checkpoint has **no actual V2 positive capture**. The independent
oracle must keep actual observations PENDING until the complete internal native
pipeline writes and reopens a real decision. Do not import production financial
functions to construct the independent expected values.

All JSON is UTF-8 `json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=True,
allow_nan=False)`. Unknown/missing fields, duplicate keys, floating JSON metadata,
nonstandard numbers, bool in integer fields and noncanonical representations are
invalid. Metadata integers fit signed64 where applicable. Monetary unit strings
are canonical ASCII integers with absolute magnitude less than 10^38; negative
zero, leading zeros, signs on positive numbers, exponent and Unicode digits are
invalid. Amounts/risk values are exact decimal strings. USD and BTC scales are8
in this first internal format. No float or Decimal context rounding may affect
native-unit transitions. Policy/catalog/market decimal inputs retain their exact
public schema and controlled model precision, with no implicit currency netting.

## Export bundle and content identities

The replay export is a self-contained bundle with exact `BUNDLE_FIELDS`:

| Field | Exact retained object |
| --- | --- |
| `format` | integer2 |
| `decision` | Actual `uta_credit_decisions` SQL row, with its canonical `payload` text |
| `market` | Actual base `uta_market_history` row: snapshot_id/content_digest/payload/origin/recorded_at |
| `artifact` | Actual dedicated `uta_credit_code_artifacts` row: artifact_id/manifest text |
| `policy` | Actual dedicated `uta_credit_risk_policies` row: policy_id/payload text |

The decision payload is exact `DECISION_FIELDS`. The primary `decision_id` is
`credit-decision:sha256(canonical(payload))`, without a self-referential ID in
that payload. Planned `operation_id` is
`credit-operation:sha256(canonical(['BORROW',account_id,command_id]))`. This ID
is known before effects; the decision content ID is known only after actual
post-state and last-check evidence. Each duplicated SQL identity/version/time
must equal its payload counterpart. Artifact ID is the existing
`credit-artifact:sha256(canonical(manifest))`; dedicated policy ID is
`credit-risk-policy:sha256(canonical(policy))`; market SID is
`market:sha256(original payload UTF-8)`, with the same independent content_digest.

The full capability canonical text is in `capability_payload`, with its V2
`credit-internal-v2:` content ID in `capability_id`. `static_budget` is the
original canonical static descriptor text, and `descriptor_id` keeps its original
`credit-native:` identity; it is never silently renamed to the capability ID.
Static certificate allocations/claims are complete across all declared shards,
but actual admission consumes only the immutable local allocation. No UNKNOWN
or unavailable shard releases or reallocates budget.

## States, amounts and journal

`pre_state` has exact `PRE_STATE_FIELDS`, generated from actual SQL by native
scope before any protected financial effect and persisted/hash-bound in the
actual intent. `post_state` has exact `POST_STATE_FIELDS`, read from the same
real financial transaction after the effect. Public frozen Python objects are
not verification seals; complete capture must compare them to actual native
prestate and actual current rows.

`account` has exact `ACCOUNT_FIELDS`: original signed balances; frozen native
asset amounts; positions by symbol with exact signed quantity and cost_basis;
liabilities as ordered `{asset,principal,interest}` rows; complete original live
order rows; boolean halt, version and nullable original liquidation state.
Order quantities, limits, cumulative fills/fees and reduce-only retain their
actual stored types/units. Reserve is recomputed from the full original order
state, actual policy fee/rates and original market. Multiplier and settlement
come from the retained catalog; risk equity is quoted in synthetic USD.

`credit` has exact `CREDIT_FIELDS`. Every field except integer `version` is a
native BTC minor-unit string. Cash is signed; principal/interest are separately
nonnegative; their liability ledger balances are separately negative. Local
aggregate principal/interest equal the corresponding gross receivable accounts.
`limits` is the exact two nonnegative BTC native-unit limits. `quote_units` and
`quantity_step_units` are BTC native-unit strings; the quote must independently
recompute from the complete actual pre-state/catalog/rules/market and order
reserve. Matching a supplied quote alone is insufficient.

`gross_components` contains `before` and `after`, each with exact `GROSS_FIELDS`.
These are explicit nonzero-amount maps derived from original signed balances
and separate liabilities: positive gross assets, absolute negative cash deficits,
principal, interest. They must agree with the original account and credit rows.
Cash deficits use full price in risk debt, remain outside the native principal+
interest quantity budget, and are never netted against positive assets/loans.

`journal` has exact `JOURNAL_FIELDS`, taken from actual `ledger_events` and
`ledger_postings ORDER BY ordinal`, with integer sealed=1 and a positive integer
sequence. Each posting has exact `POSTING_FIELDS`; ordinal is contiguous integer
0..N-1, never bool. Units are exact signed BTC integer strings. The four borrow
legs are sorted lexicographically by account then asset:

1. `customer:<account>` +quantity
2. `liability:principal:<account>` -quantity
3. `system:credit-pool` -quantity
4. `system:credit-principal-receivable` +quantity

Journal identity is the original `CreditService` journal event key, not a newly
invented ID. Fingerprint/hash use the actual retained ledger algorithm. Its
sequence is prestate journal_head.sequence+1 and previous_hash equals the actual
prestate head hash. Pool funding evidence is a list of actual pre-activation
`{command,journal}` pairs, ordered by original credit command ID, including their
original source reference, result bytes and original sealed two-leg funding
journal. These are synthetic accounting claims, not proof of external custody.

`receipt` is the original financial credit result, including original CID,
account, asset/amount, p/i/total, account version, journal and risk evidence.
It contains no self-referential decision ID. Native closure requires its bytes
to match the actual immutable credit record and actual durable SUCCEEDED result.
The decision is found by its unique stable operation ID/account/CID.

## Source and clock

`source` has exact `SOURCE_FIELDS`, read from actual `credit_v2_sources`. Its
`payload` is the canonical full receipt with exact `SOURCE_RECEIPT_FIELDS`.
Source ID is `credit-source:sha256(payload UTF-8)`. The receipt uses integer
format2, source_kind `synthetic_local`, actual actor/reference/authority,
account/CID/kind and actual canonical inbox `command_payload` text; payload_hash
is SHA256 of that command text, without any runtime token/nonce. accepted_at is
the real producer UTC checkpoint with six microsecond digits and `+00:00`.
No HMAC or customer permission claim is implied by this source kind.

Producer commits first-source+PENDING first. The financial COMMIT binds that
same source to intent, effect, full decision, sealed journal, immutable credit
record and terminal receipt. Rollback preserves accepted producer metadata and
removes financial intent/effects/audit. A legacy receipt has no invented source,
inbox or decision; original legacy queries remain no-new-effect.

selected_at is the original actual native selection check, duplicated in
pre_state and the decision. last_checked_at and recorded_at are actual exchange
UTC checkpoints during completion. All use explicit `+00:00` and either exact
seconds or six microsecond digits, with selected<=last_checked<=recorded.
Both recorded market checks use the same actual SID/payload. Staleness is
`age>max_age`; equality is allowed. Future observation is rejected when
`age<-1second`; equality is allowed. POLICY_FIELDS explicitly retain this skew
and the actual base policy. Replay validates recorded checkpoints, never today's
clock. Native before-COMMIT rechecks actual now/sameSID/freshness again.
`physical_commit_at` is always null: no hard real-time physical COMMIT instant
is fabricated or inferred from recorded_at.

## Repayment and independence boundary

This dedicated decision contract accepts only CREDIT_BORROWED. REPAY creates no
borrow decision, SID or quote: market_dependency NONE, source/FIFO/intent/sealed
journal/credit receipt/terminal still close atomically. Principal-only and
interest-only repayment have four legs; mixed repayment has seven. Interest is
paid first, pool receives only repaid principal, native debt budget decreases
by paid principal+interest. Original account cash/debt/gross receivables remain
separate. A later repayment observation export must identify actual versus
arithmetically derived fields; it cannot invent a fresh risk valuation.

Independent Fraction/integer expected results and journal normalization must
not import production core functions. Real first-source acceptance, same
transaction/COMMIT, scope, restart and unknown handling remain runtime
observations with original source/command IDs and reopened storage. Pure fixtures
with null actual observations remain PENDING, regardless of arithmetic matches.

## Inner field and integer-algorithm clarification

Both account_limit_units and local_asset_limit_units constrain **gross
principal+interest**, not principal alone. The account limit applies to this
account's BTC quantity. The local asset limit and sealed allocation each apply
to the sum of gross BTC principal+interest across this actual shard. Cash deficits
affect risk debt in USD but do not consume that BTC quantity budget. Comparisons
are inclusive; a requested addition exactly at a limit is allowed if every
other gate passes. The quote/quantity-step constraint is separate.

Journal fingerprint is lowercase SHA256 of UTF-8 canonical JSON
`[[account,asset,integer_units],...]`, with exact JSON integer units (converted
from bounded canonical strings) and the original normalized posting order.
Event hash is lowercase SHA256 of canonical JSON
`[sequence,event_id,previous_hash,fingerprint]`. Event ID for credit scope is
`credit:sha256(canonical(['account:'+account_id,command_id]))`; funding uses
`credit:sha256(canonical(['pool',command_id]))`. Funding legs sort capital debit
before pool credit. No imported production hash function is needed by the oracle.

The added BASE_POLICY_FIELDS, ORDER_FIELDS, RISK_FIELDS, RECEIPT_FIELDS and
RECEIPT_RISK_FIELDS in the normative code specify exact inner keys:

- Base policy format is integer1, risk_mode phase1_cross, fee_rate string0,
  order_precision integer8, scales USD8/BTC8; max_price_age_us is a positive
  integer at most five minutes. Catalog and rules use their complete published
  canonical object schemas. reserve_formula is
  `linear-adverse-loss-cumulative-fee-v1`; both execution cache capacities are
  integer0. Complete rule/catalog/version IDs are retained.
- Orders are the actual schema3 live rows, status OPEN/PARTIALLY_FILLED, with
  integer reduce_only0/1 and version; account/order/symbol/created_at are strings;
  admission_decision_id is a string (nullable only where the original legacy
  audited upgrade explicitly permits it). Quantity, limit, filled quantity,
  cumulative fee_notional and charged_fee are exact decimal strings. Positions
  retain signed quantity and cost_basis; liabilities are sorted asset/p/i rows.
- Every numeric financial risk field is an exact USD decimal string;
  account_version, market_version, rule_version and catalog_version are integers.
  equity aliases risk_equity. borrowable maps asset to native-asset decimal
  quantity strings. margin_ratio is equity/MM (risk worsening direction down),
  nullable when MM=0, rounded with decimal precision34/half-even exactly as the
  original API diagnostic; it is never an admission quantity or a replacement
  for exact equity/MM boundary checks. status is HEALTHY/MARGIN_CALL/LIQUIDATION.
  observed_at/market_id identify the original market; risk_mode is phase1_cross,
  rule_id is the complete retained rule's identifier.
- Receipt p/i/total/amount are native BTC decimal strings, with total=p+i;
  account_version is the actual post-version. risk_evidence carries the actual
  original pre-borrow conservative borrowable quantity and original market
  version/time, plus the original projected risk/versions. Borrowable_before is
  a decimal string here, never null because this format requires Cross rules.
  The full pre/post risk remains separately retained.

The bundle is necessary for numerical/operation replay but cannot by itself
prove that SQL COMMIT happened. Independent actual observation must separately
read the original inbox/source/intent/expected-postings/credit-command/decision/
ledger/terminal rows from reopened storage, check their actual IDs/hashes and
versions, and retain the original command/response-loss/restart evidence.
