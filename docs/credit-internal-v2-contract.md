# Internal synthetic credit V2: schema and positive-chain acceptance contract

This is the first code contract on a new branch descended from immutable
`899c91d`. Format1 NATIVE_PREPARED is never promoted or unlocked. V2 is for
new synthetic authorities only, defaults off, and has no HTTP/CLI enablement or
new public borrow route. Public/CLI new managed borrow keeps 501. Real funds,
HMAC first-source, lending liquidation/insurance/ADL and production GO remain
blocked. Schema code alone is incomplete and cannot acquire ownership or READY.

## Scope and authoritative identities

The first positive internal chain uses batch0/cache0, USD settlement and BTC
borrowing, explicit zero new interest/fee and immutable offline shard allocation.
Opening synthetic principal/interest is allowed only after complete original
ledger/credit verification. New pool funding or interest accrual after activation
is unsupported. Repayment follows the existing interest-first algorithm and
has market dependency NONE, including halt and unavailable/stale market.

The queue's original CID remains the business idempotency key. A planned borrow
operation ID is `credit-operation:sha256(canonical(['BORROW', account, CID]))`.
This known identity is distinct from the full content-addressed decision ID,
which cannot be known before the actual final time/state evidence exists.

The real immutable first-source receipt and PENDING inbox row are accepted
together by the restricted producer transaction. The later financial transaction
references that original receipt; it does not claim the source was first
inserted with the loan. A financial rollback preserves accepted PENDING/source
metadata and removes all financial effects, intent and decision. Retrying with
the same business data preserves the first source. No generic enqueue or public
repayment path may fabricate a synthetic source implicitly.

## Dedicated audit schema in executable code

`uta.credit_audit_v2` defines exact compiled SQL for three independent tables,
two parent indexes and nine immutable/no-replace triggers:

| Object | Exact responsibility |
| --- | --- |
| `uta_credit_code_artifacts` | Real complete credit artifact manifest under its canonical content identity |
| `uta_credit_risk_policies` | Complete versioned actual risk/catalog/scales/fees/freshness policy bytes |
| `uta_credit_decisions` | Full `CREDIT_BORROWED` evidence under a content-addressed decision ID, unique stable operation ID and original account/CID |
| Inbox composite parent | Deferred `(CID, account, BORROW, SUCCEEDED)` obligation to the actual durable inbox |
| Journal composite parent | Deferred `(journal_id, sealed=1)` obligation to the actual sealed event |

The decision row explicitly carries account/command, asset/amount, business
payload hash, original source ID, original market SID, actual artifact/policy,
native descriptor/allocation IDs, journal, before/after integer versions and
selection/final-check/record times. Full canonical payload bytes contain the
corresponding immutable input documents, observed states and complete actual
journal legs. The dedicated reader must verify the content hash and every
duplicated relational identity before numerical or operation replay.

The native write-before intent binds stable operation ID, not a fabricated
future decision content hash. Its deferred composite FK targets
`(operation_id, kind, account_id, command_id, journal_id)` on the dedicated
decision table. The full decision is inserted after actual effects and final
freshness/risk checks, before closing the credit record. Native closure and
before-COMMIT inspect actual staged source/intent/decision/journal/credit/terminal
rows in both directions. Repayment does not create a borrow decision; its own
source/intent/4-or-7 legs/receipt/terminal obligations still close atomically.

The module currently defines/verifies the catalog and stable operation key. It
does not install itself, capture a decision or enable execution. Native-v2 must
add its actual financial/producer/DDL guards and register the complete compiled
inventory atomically. Existing base audit history and gaps are not rewritten.

## Required actual positive acceptance

| ID | Required runnable observation before positive V2 acceptance |
| --- | --- |
| CV2-01 | Full fresh installer validates all source/claim/budget/SQL/audit/code/FIFO capabilities; partial install rolls back and cannot acquire/READY |
| CV2-02 | Original PREPARED1 always refuses owner and financial writes; actual old binaries refuse V2; no-cap paths preserve original behavior |
| CV2-03 | Synthetic source+PENDING commit, per-account FIFO, real internal BORROW admission and actual four-leg funded loan, gross debt, dedicated decision, credit receipt and original CID terminal in one financial COMMIT |
| CV2-04 | Actual original SID/payload, two real captured check times, clock bounds/freshness at both checkpoints and final same SID; no today's-clock fiction or fabricated physical-COMMIT time |
| CV2-05 | Replay reconstructs actual gross assets, cash deficits, p/i, freezes, orders/positions, reserve, quote, limits, allocation, pool/receivables, version transition and ordered journal; generic risk-only match cannot pass |
| CV2-06 | Quote/step/limit/pool/margin business refusal causes real SAVEPOINT rollback, no effects/decision/intent; terminal rejection references the original source and CID |
| CV2-07 | Late financial validation failure caught by caller cannot COMMIT; actual staged obligations survive or roll back exactly with SQL SAVEPOINT, never mutable in-memory counters |
| CV2-08 | Response lost after actual COMMIT, same CID query/retry, process restart and storage reopen produce the original terminal result with no extra loan/journal/source/decision |
| CV2-09 | Unknown result/storage/source/budget never releases allocation, creates a replacement CID or dynamically borrows another shard's budget |
| CV2-10 | REPAY uses actual existing FIFO and source, pays interest then principal in four or seven legs and succeeds during halt/market outage without calculating/fabricating a fresh quote |
| CV2-11 | Legacy receipt replay returns the original result without backfilled decision or new effect; missing-inbox legacy POST remains rejected until explicit compatibility is implemented |
| CV2-12 | Partial/corrupt code, policy, market, source, ledger, intent, terminal or decision fails typed closed; signed permissions/HMAC and loan distress remain explicit production gaps |

These are implementation acceptance gates, not claims that this first schema
commit has passed them. Each following runnable slice retains actual tempDB
evidence with commit/source hashes, start/end, raw outcomes and independent
review. Small internal tests use CPU3/4, at most 60s per batch; no pressure,
long jobs or frozen/live sources are changed.

The first actual schema slice passed five Python3.12 tests (0.198s): creating
the compiled catalog on self-created temporary databases, exact parent
references/reopen verification, missing/unexpected object rejection without
repair, and stable business-operation identity. No credit decision row was
inserted. The module did not install itself or grant a native owner. Exact
source hashes, begin/end, command and raw output are retained in
`evidence/runs/credit-v2-audit-schema/`. Actual FK closure, capture and positive
financial admission remain unimplemented at this schema checkpoint.

An additional catalog correction covers every unique decision identity in the
no-replace trigger: decision content ID, stable operation ID, and
`(kind,account,CID)`. Protecting only the primary key would not preserve all
identities under `INSERT OR REPLACE` with recursive delete triggers disabled.
Six tests passed (0.640s), including actual duplicate replacement attempts on an
explicitly invalid, uncommitted SQL-only candidate. The candidate has no native
source, intent or journal; it and both archive rows are always rolled back and
never represented as a valid credit decision or successful loan. Raw evidence is
in `evidence/runs/credit-v2-audit-unique-identities/`.

Read/capture building blocks now include a same-connection financial credit
snapshot (gross p/i/receivables/cash/pool), persisted runtime-policy binding,
strict retained JSON/UTC parsing, historical checkpoint freshness and actual
sealed journal/hash/head verification. Repayment reads skip all borrow limits
and market queries; recorded after-state may use the terminal integer version
without requiring another increment. These helpers do not grant context or
create a decision. Actual V2 capture/dispatch remains pending.

Nineteen component tests per runtime passed on Python3.12 (0.746s), 3.10
(0.717s), and3.13 (0.818s), each with ResourceWarning treated as an error. They
include actual preseal financial reads and journal COMMIT/reopen, the six catalog
cases and seven source/data cases. The source structural-COMMIT residual remains
explicit; no V2 owner or credit decision was created. All commands, begin/end,
source hashes and raw output are in `evidence/runs/credit-v2-audit-read-helpers/`.

Rollback of this unwired schema slice is a code revert. A later persisted fresh
V2 authority cannot be downgraded by deleting markers, changing allocation or
rewinding financial history; forward recovery must reconcile the original CID
and preserve committed effects. No production deployment is authorized here.
