# Fresh internal credit V2: native schema and API contract

This contract starts from `899c91d0a032d88cc4cb8c73ffb09cb2d1bd7236` and uses the
parent-owned audit catalog `3a434f2d33f7fcf020f31cf78cc59f1388a99031` (local
dependency copy `084e29e`). The new `uta.credit_native_v2` module contains only
compiled schema definitions and immutable-identity triggers. It has **no
installer, recognized writer marker, positive UDF, acquire, scope or intake**.
The code contract does not satisfy the positive-chain gates below. No SQL has
been executed for this schema slice, so FK closure and runtime semantics remain
unverified. No PREPARED1 source or behavior changes.

## Scope and irreversible authority boundary

The intended positive capability is a new fresh-only format2 authority, with
explicit internal synthetic entry points, USD settlement, BTC scale8 borrowing,
zero new credit interest/fee, batch0 and both caches0. Fully verified synthetic
opening principal and interest may exist; repayment uses the original
interest-first algorithm and four or seven actual legs. It has market dependency
NONE. New pool funding, new interest accrual, dynamic allocation, cross-shard
borrowing, USDT/USDC, auto-borrow, HTTP, CLI and HMAC sources are unsupported.
Existing no-cap behavior and original CID replay precede any new-operation gate.

The proposed marker is the separate reserved table
`writer_fence_credit_v2_capability`, format2, state `SYNTHETIC_INTERNAL`, with a
content-addressed envelope. Existing `writer_fence_credit_capability` remains
format1 forever; its presence, a prior owner generation/event, batch capability,
any partial credit schema, nonempty inbox or prior V2 marker excludes the fresh
installer. There is no PREPARED-to-active transition or marker replacement.
An identical already-complete V2 installation may be verified and returned
without any DDL or new activation; different envelope bytes conflict.
Old actual binaries must reject V2's unknown reserved inventory, not silently
become an old writer. The new loader must recognize partial `credit_v2_*` and
credit-audit inventories even if a marker is missing.

The proposed strict envelope binds actual authority/shard, the original format1
static budget declaration and its ID, current credit artifact, audit2/source2/
FIFO2/native2 formats, BTC/USD scope, batch/cache zeroes and explicit synthetic
status. Budget format1 is used as a validated declaration, never as an activation
flag. All real schemas, funding references, opening financial verification,
artifact contents, versioned policy and actual FIFO implementation must pass in
one original control write transaction **before** the marker/event are published.
No caller-supplied `ready`, `verified`, successful callback or Python boolean can
substitute for these checks. Publication failure rolls back all new objects.
The exact envelope keys are `format`, `stage`, `synthetic`, `authority_id`,
`shard`, `static_budget`, `static_budget_id`, `audit_format`, `source_format`,
`fifo_format`, `native_format`, `artifact_id`, `settlement_asset`, `borrow_asset`,
`batch_size`, `reserve_cache_size`, `market_cache_size`, `production_approved`.
The fixed values are format/audit/source/FIFO/native2, stage
`SYNTHETIC_INTERNAL`, synthetic true, USD/BTC, all three numeric sizes zero and
production approval false. The static budget remains the strict original
descriptor. Marker `capability_id` is `credit-internal-v2:` plus the SHA256 of
the complete canonical envelope. Audit/intent/allocation `descriptor_id` stays
the original static-budget descriptor ID, matching the already validated pure
transition contract; it is not relabeled as a new active capability. The safe
context view and future full audit payload also retain the V2 capability ID.

An explicit internal `acquire_credit_v2` path is proposed. Existing generic
acquire/CLI/startup must not automatically opt into V2. Each V2 acquire and
transaction load verifies the complete persistent capability and current real
artifact. The financial transaction rechecks its native capabilities and actual
loaded artifact before physical COMMIT. Original nonce/PID/thread/generation/
boot/expiry checks remain in force; no new role or caller COMMIT is granted.

## Concrete native catalog

`uta.credit_native_v2.TABLE_SQL`, `INDEX_SQL`, `TRIGGER_SQL` and `OBJECT_SQL` are
the proposed exact definitions. Financial units use canonical ASCII signed or
unsigned TEXT with magnitude below `10**38`; they are never cast to SQLite
REAL/INTEGER for financial arithmetic. Type/format checks do not prove financial
meaning; that requires the actual typed scope and staged-row verifier.

| Table | Stored identity and obligation |
| --- | --- |
| `credit_v2_config` | Immutable envelope/static-budget/artifact IDs, actual opening ledger/credit watermarks and canonical verified opening state |
| `credit_v2_allocations` | Actual local immutable certificate allocation, authority, shard, BTC scale8 and limit; no reallocation or global live sum |
| `credit_v2_sources` | CID primary key; unique source ID and source reference; actual account/kind/canonical inbox payload/hash, `synthetic_local` actor, authority and complete canonical source receipt |
| `credit_v2_intents` | CID primary key, unique journal and planned operation key, original source/allocation, exact pre/post debt/version, expected leg count, canonical prestate/isolation snapshots and digest |
| `credit_v2_expected_postings` | Original CID, actual canonical sorted ordinal, account, BTC and signed integer units; generated by trusted actual financial inputs |
| `credit_v2_legacy_commands` | Exact existing receipt identities/result hashes frozen at installation, with no fabricated historical audit |

The catalog defines 18 UPDATE/DELETE/REPLACE refusal triggers. REPLACE checks all
independent UNIQUE identities, including source ID/reference and intent
operation/journal IDs, not only each primary key. This avoids relying on DELETE
trigger behavior under SQLite's default `recursive_triggers=OFF`. The runtime
slice must add real source, intent, effect and closing authorization gates plus
the existing native writer guards on all native and dedicated audit tables.

All borrow intent FKs are deferred and required fields are NOT NULL: real inbox
`(CID,account,BORROW,SUCCEEDED)`, actual credit receipt tuple, sealed journal,
allocation/authority/asset, original first-source tuple and actual market SID.
The audit obligation targets the parent's exact
`uta_credit_decisions(operation_id,kind,account_id,command_id,journal_id)` unique
identity. `operation_id` is the stable `borrow_operation_id(account,CID)`; it is
**not** a full decision content hash. The true decision ID is computed only
after actual last-check time and complete post-effect evidence exist. Repay
uses NULL audit operation/kind/SID and literal market dependency NONE, with all
other source/intent/receipt/sealed-journal/terminal obligations intact.

Dedicated audit definitions stay parent-owned. Audit/source/allocation/descriptor
identity relationships absent from a single FK must be checked in both directions
by real SQL gates and the before-COMMIT validator, not inferred from an outgoing
FK or a supplied expected-row fixture.

## Internal API and source protocol

The following are planned implementation interfaces, not callable stubs that
grant permission:

* `install_internal_credit_v2(database, exchange, credit, envelope)` performs
  real fresh-only preflight and atomic complete-catalog publication. It must
  call the actual audit/FIFO validators, not accept verifier callbacks.
* `acquire_credit_v2(database, owner_nonce, ttl_seconds)` is an explicit internal
  fenced owner acquisition after all actual capabilities verify.
* `synthetic_intake_scope(database, connection, *, canonical_source)` is restricted
  to the real inbox role, exact connection/authority/PID/thread and canonical
  synthetic actor/payload. It supplies no financial token or borrowed allowance.
* `operation_scope(credit, connection, *, command_id)` reads the actual eligible
  PENDING head and original source, generates trusted prestate/transition/4-or-7
  legs, and stages the intent before any protected effect. It accepts no caller
  expected legs, prestate, source replacement or successful authorization hook.
* `assert_operation_context(credit, connection, *, command_id, account_id,
  asset, amount, operation_kind='BORROW')` rechecks actual connection, role,
  process/thread, token and staged intent. It returns a safe frozen
  `CreditOperationView`, not a transferable capability or cached success flag.
* The fixed final verifier reads actual staged rows and actual final risk via
  parent-owned audit functions before the original `Database` physical COMMIT.

Source columns are fixed as `command_id`, `source_id`, `account_id`, `kind`,
`payload_hash`, `source_kind`, `actor_id`, `source_reference`, `authority_id`,
`command_payload`, `payload`. `command_payload` is the canonical actual inbox
business payload. `payload` is the full canonical source receipt, containing
the original actor/reference/authority and business identity. IDs/digests are
validated from these actual bytes. No HMAC permission is implied.
Its exact receipt keys are `format` (integer2), `source_kind`, `actor_id`,
`source_reference`, `authority_id`, `account_id`, `command_id`, `kind`,
`payload_hash`, `command_payload`, `accepted_at`. `source_id` is
`credit-source:` plus SHA256 of the canonical complete receipt's UTF-8 bytes;
`payload_hash` is SHA256 of the exact canonical `command_payload` UTF-8 bytes.
`accepted_at` is the actual producer's canonical UTC `+00:00` time. All redundant
relational values must equal the corresponding receipt fields. There is no
caller-selected source ID or runtime nonce in that document.

Source is inserted first inside the restricted producer transaction; its exact
inbox FK is deferred. The credit inbox INSERT gate then requires the actual
matching source. This avoids an immediate-EXISTS cycle while source+PENDING
commit together. Original CID replay reads and compares the existing row before
any insert. Different content/source under that CID is a conflict. Ordinary
generic enqueue/public repayment must not fabricate synthetic source metadata.
Source/PENDING persist through later financial rollback; business rejection may
commit REJECTED against the original accepted source, without an intent/effect.

## Trusted prestate, actual effects and closure

The context and immutable intent share `pre_state_payload` and `pre_state_hash`.
Their canonical object is `{account,credit,limits,selected_at,market_snapshot_id,risk,
quote_units,quantity_step_units,journal_head}`. `journal_head` is the actual last
sealed ledger `{sequence,event_hash}` (empty genesis is sequence0/hash64zeroes).
The new event must have exactly head sequence plus one and that prior hash.
`account` is the actual complete
`ExchangeService._audit_state`; `credit` is the exact existing transition
`SNAPSHOT_FIELDS` in integer units with integer version; `limits` is the exact
`LIMIT_FIELDS` for BORROW and NULL for REPAY. Repayment does not require a new
borrow limit or remaining borrowing allocation, and is never refused because
a missing/zero new-borrow limit prevents new risk. The fixed parent-owned
`read_credit_snapshot(exchange,credit,connection,account_id,asset,
require_limits=True)` SQL reader returns `(snapshot,limits)`; REPAY uses
`require_limits=False` and stores no claimed borrowing allowance. The reader
it must require a real financial joinable transaction without requiring an
already-created operation intent or conferring a role. Borrow market/risk/quote/step come from the actual same snapshot
and versioned policy. Native selection records actual `exchange._now()` as
canonical UTC `+00:00` `selected_at` and immediately validates the actual market
at that time with the configured max age and explicit future skew of one second.
Repay sets the selected-time/market/risk/quote/step fields to NULL and
does not ask for fresh prices. `isolation_payload/hash` retain nonsecret
canonical digests of actual unrelated financial state and other accounts/rows.
They must detect interleaved orders, positions, other CIDs or unrelated effects.
Publicly constructed frozen capture/view objects never establish that prestate.

Parent `CreditAuditV2.begin_borrow` runs after actual native intent staging and
checks its real reads against this native prestate, preserving the original
selected time. Effects retain the original
four-leg funded borrow, gross p/i and version bump. Parent
`complete_borrow(connection,capture,receipt)` runs after those actual effects and
before `credit_commands` INSERT, verifies native prestate binding and actual
after-state/journal/risk/freshness, then writes the full content-addressed
decision. Actual `selected_at <= last_checked_at <= recorded_at` is required;
the fixed policy includes `max_future_skew_us=1000000`. Before COMMIT a new
actual time must be at least `recorded_at`, with fresh same-SID revalidation.
These are captured application check times, not a claimed physical COMMIT time.
The closing credit-record gate checks actual complete sealed legs,
decision and intent. The inbox terminal update follows in the same transaction.

The planned native scope UDF is pure-context validation; each effect trigger
must additionally prove that its matching actual intent row exists in this
SQLite connection. It must not recursively query SQL from a UDF or count
observed callbacks as proof. SQL rollback/savepoint rollback removes rows, not
Python counters. Before COMMIT reconstruct both directions from actual staged
intent, source, expected/actual postings, credit receipt, complete audit,
terminal, debt and account/version rows; verify actual unrelated state remains
unchanged. Do not accept fixture-populated expected rows as financial authority.

Native authorization/DDL/closing or late final-gate failure poisons the real
guard even if caught; COMMIT must fail. A genuine business refusal uses the
existing actual `ROLLBACK TO durable_command` before committing only REJECTED.
Missing intent after that rollback cannot leave any financial residue. Final
market/storage/unknown outcomes are technical failures, leaving original
PENDING/source rather than inventing a new CID or releasing an unknown effect.
V2 denies financial DDL immediately and checks exact schemas without automatic
repair. Original Database transaction ownership and final lease checks remain.
Do not run original `DurableLedger.verify` while a legitimately staged intent
still lacks its deferred journal/decision/terminal parents: its full
`foreign_key_check` must reject incomplete obligations. Run full original
ledger/credit verification before intent staging and after all real terminal
obligations close; use actual local checks during the operation.

These controls validate the supported application path on the trusted host.
They are not an OS-owner boundary, generic SQL proof of portfolio math, global
cross-shard atomic allocation, replication, performance or production acceptance.

## Positive acceptance table and release/rollback

Every row below is **PENDING**, not a result of this schema commit. The parent
CV2-01..12 acceptance table remains normative and also requires independent
financial replay and review.

| Native gate | Required actual observation |
| --- | --- |
| NV2-01 | Fresh complete installation, original full financial/claim verification, real audit/FIFO/current-code validation; partial installation rollback leaves no marker or objects |
| NV2-02 | Original PREPARED1 cannot unlock; old actual 458/899 binaries reject V2; no-cap positive contracts remain intact; generic acquire does not opt in |
| NV2-03 | First-source/PENDING actual COMMIT, FIFO actual selection, real owner/scope, four-leg borrow, dedicated audit, original CID SUCCEEDED, storage reopen and original receipt recovery |
| NV2-04 | Missing/wrong source, intent, allocation, audit, sealed journal, receipt or terminal rejects actual COMMIT with genuine SQLite constraint/error classification |
| NV2-05 | Canonical four/seven legs generated from actual prestate; wrong expected metadata, forged capture/view, changed position/order/other CID or pooled debt masked by another account rejects |
| NV2-06 | Actual SAVEPOINT business rollback removes intent/audit/receipt/legs/debt/version changes and permits only original-CID REJECTED; no observed-callback counter proof |
| NV2-07 | Late freshness/risk/closing failure caught by caller, missing staged intent after rollback, expired/foreign token, wrong PID/thread/role/connection and caught DDL denial all fail physical COMMIT |
| NV2-08 | Internal sourced REPAY pays real interest then principal, four/seven legs, no fresh market during halt/outage; generic public/queue source shortcuts reject |
| NV2-09 | REPLACE/UPSERT/UPDATE/DELETE against all immutable unique identities fails; actual foreign_keys is ON and attempts to disable it poison the guarded transaction |
| NV2-10 | Lost result, restart, same CID retry/query and original source give one committed loan and no duplicate journal/debt/audit; unknown outcomes remain queryable and unreallocated |

No migration/activation command is shipped here. Schema review is followed by a
separate real primitive commit, actual temporary SQLite tests (CPU4, each batch
at most60s, explicit begin/end/raw) and peer acceptance. No listener, pressure
load, live/frozen authority or long-running job is used. Pre-publication failure
rolls back; after successful future publication there is no marker deletion,
format downgrade or static budget reassignment. Recover forward under original
CID reconciliation. A full positive internal chain still provides no real-funds
or production GO.

The final schema-only check is reproducible as:

```sh
taskset -c 4 timeout 5s python3 -W error::ResourceWarning evidence/runs/credit-native-v2-schema-contract/check_catalog.py
```

This parses Python, imports the inert catalog, counts its definitions and checks
that positive APIs are absent. It does not execute SQL or verify FK/trigger
semantics. The original early catalog check is retained separately; subsequent
capability/static-descriptor identity separation is checked in the final raw
with its actual source hash. Neither output is a financial or runtime pass.

## First real source/data primitives, without an active authority

The next code slice implements `validate_envelope`, `source_receipt`,
`parse_source` and `read_source`. Their frozen outputs remain declarations or
evidence, not permissions. The source constructor records UTC with six
microsecond digits and `+00:00`; the strict parser requires those exact canonical
bytes. `read_source` reads actual source and inbox rows and compares every
duplicated identity with the full canonical receipt and the expected authority.
No archived field chooses an import, filename or executable symbol. Unknown
scope, bool-as-format, noncanonical numbers, duplicate keys and unknown fields
fail typed closed. There is still no installer, native owner, active operation
scope, intake scope, successful authorization UDF or positive borrower.

Seven actual component tests passed on Python3.12 in 0.173s, actual process
window 2026-11-17 12:46:38.669179 through 12:46:39.008421 UTC (0.339435691s),
CPU4, ResourceWarning errors enabled. The self-created private temporary SQLite
fixtures reuse real core ledger/credit/inbox/base-audit parents. Their explicit
raw component connection isolates schema/reader behavior; it does not claim a
native owner or runtime authorization. No successful permission callback exists.
Source followed by its matching PENDING row actually commits and reopens. A
source without its deferred inbox parent fails actual COMMIT with native code
787 and leaves no source/inbox after rollback/reopen. Three independent UNIQUE
REPLACE identities are blocked with native 1811 under recursive_triggers OFF.

The component deliberately retains a remaining boundary: without the future
native intake UDF, raw component SQL can commit a structurally valid source row
whose actor column differs from its receipt; the real reader rejects it typed.
This is not a valid source or positive permission test. Runtime source/effect
gates, exact writer inventory, complete audit/FIFO validation and all NV2 gates
remain pending. No loan, dedicated decision, financial native effect or owner
was produced. Exact hashes, command, first unchanged output and begin/end are
in `evidence/runs/credit-native-v2-primitives/`.

```sh
taskset -c 4 timeout 30s python3 -W error::ResourceWarning -m unittest tests.test_credit_native_v2_primitives -v
```
