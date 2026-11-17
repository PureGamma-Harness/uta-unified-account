# Independent native PREPARED credit review: a4d4fac

Reviewed source: `a4d4facc3235a324afbc0fdb19635bf0bbc86a75`.
Integration base: `8338beefbe4f90ab8474f66ddad2d2d230ed7d76`.

**Scoped verdict: no blocker identified for this default-off, nontrading
PREPARED format.** This review covers `credit_policy`, `credit_native` and
their writer-fence/storage contract. It explicitly excludes the separate
loaded credit-artifact identity review and its known omissions under repair.
It does not approve positive credit operations, financial/model sign-off,
release qualification or production use.

All work was static reading of this exact Git source, ASTs, archived raw
results and pinned old-binary archives in an isolated review tree. No SQL,
service, test, native preparation, sample, old job or clone was executed or
accessed by this reviewer. The mutable author's worktree and later artifact
changes were not used for this verdict.

## Policy is a bounded declaration, not authority

The policy parser accepts only explicit synthetic NATIVE_PREPARED format1,
zero new interest/borrowing fee, required managed inbox and credit batch zero.
Production approval, ACTIVE/verified fields, unknown fields, duplicate JSON
keys, floating or nonfinite JSON values, noncanonical unit strings, booleans
as metadata integers, excess bytes/nodes/depth and custom object types are
rejected by the source checks. Monetary units are ASCII decimal integer
strings bounded below 10^38, with explicit per-asset scale; they are not
coerced through float or SQLite CAST.

The full certificate enumerates unique contiguous authorities, every asset's
allocation to every authority, nonnegative opening gross principal/interest
and pool, and unique funding claims. Per-asset allocation sums cannot exceed
the declared global limit; each opening principal-plus-interest cannot exceed
its shard allocation. Funding claim sums must cover the opening pool without
overflow. Pool liquidity is not equated to the lending limit and assets/debt
are not netted. Content IDs bind canonical policy/certificate/descriptor
bytes; supplied external expected identities are checked when provided.

The native installer binds the actual current authority and ledger scales.
Other authorities, global layout and external custody/source declarations in
the operator-supplied certificate are not independently proved by a single
local preparation. Immutable typed return objects and their explicitly
limited validation_scope do not grant credit, readiness, global budget
reallocation or funding ownership. In particular this stage does not
implement positive borrowing, HMAC source capture or an operation replay.

## Fresh preparation and complete source validation

`prepare_credit_native()` requires a real unbound Database and executes in its
original control write transaction. `_load` validates the persisted authority
and original guards. A first preparation requires generation zero, empty
owner and unused inbox, with exactly the enabled_guard_v1 event or that event
followed by batches_enabled. Any prior acquire/release, extra control history,
partial native schema, conflicting descriptor or unsupported state fails;
the installer does not promote an already used account.

After DecisionAudit schema validation and before the first native DDL, it
calls the original `DurableLedger.verify(connection=...)` and
`CreditService._verify(...)` on that exact control-transaction connection.
Local immutable views expose only original read/codec methods, not service
constructors, posting/borrow methods, a new transaction, fabricated startup
verification or a writer token. Exceptions become the fixed
credit_financial_source_invalid error with their internal cause preserved.

The original ledger verifier checks integrity/FKs, scales/protection,
contiguous sealed journal history, posting sequence, per-currency balance,
event hashes/fingerprints and the complete reconstructed balance projection.
The original credit verifier checks liabilities per existing account/asset,
gross debt/receivable equality and nonnegative bounded values, stored limits,
credit command structures and nonnegative pool balances. Thus local aggregate
opening checks cannot conceal the tested negative/positive-account offset,
debt/ledger mismatch, pool/journal mismatch or missing journal protection.
Schema corruption or orphaned references are not repaired.

Only then does `validate_opening` compare the actual local principal,
interest, pool and each pool_funded source/CID/amount with the certificate.
Its aggregate checks supplement, rather than replace, those complete source
verifiers. Descriptor facts about other shards remain declarations.

## Fixed native SQL and transaction roles

The compiled native schema includes immutable/no-replace rows, composite
parent keys, deferred references and operation/posting/credit-record shells.
There are 42 compiled native objects plus the capability marker; installed
writer guards, marker control guards and SQLite implicit indexes are
additional verified objects, not a claim that the entire catalog contains
only 43 objects. `verify_schema` checks type/table/SQL for the exact native
namespace and native-table inventory, while original control and financial
guard verification remain independent.

The internal object installer accepts only a compiled object name on the
exact registered control connection. Ordinary control authorizer DDL stays
denied; its temporary privileged context is the fixed internal installation
path, not a public arbitrary-SQL permission. Preparation data, original
legacy receipt hashes, guards, marker and prepared event are committed in
that same write transaction. A failure causes the original Database rollback;
no partial schema or advanced generation may be accepted as a successful
preparation. Physical WAL/SHM byte identity is not claimed.

Load requires the marker, canonical descriptor/policy/certificate/local
allocation archive, fresh two/three-event history, generation zero and no
owner. The prepared event is bounded to sequence2 or3, so detecting a missing
marker does not require scanning every ordinary authority renewal. Missing or
weakened objects, disappeared marker/event or extra successor events fail
closed, without automatic repair. Repeating the same descriptor only verifies
and returns the same nontrading stage; a new descriptor conflicts.

## No trading authority and default compatibility

`TRADING_FORMATS` is an empty tuple. Prepared acquire and token validation
raise credit_not_active. The transaction authorizer rejects all noncontrol
financial/producer/batch-metadata DML and DDL immediately for this format;
catching the SQLite error does not clear the fatal guard. The actual registered
credit-operation UDF returns zero and poisons the transaction. No successful
operation scope, activation method, READY promotion, CLI flag, managed route,
repayment exception or forged-token path is supplied.

This deliberate exclusion includes risk-reducing trading actions on a
PREPARED authority. It is suitable only for a fresh offline synthetic layout,
not an upgrade to a live account expected to continue repayment/trading.
Deployment must retain the closed state and use reviewed forward recovery;
deleting capability, regressing generation, restoring away confirmed funds
or running an old binary is not a rollback strategy.

Absent the explicit capability, no native objects are created. The original
financial authorizer path remains, with the old base/batch inventories
explicitly preserved. The patch adds bounded native-prefix checks and thread
metadata, so unchanged default financial semantics is not a measured zero
overhead claim. Storage, credit service, managed process, gateway and CLI
source files are unchanged relative to the integration base.

## Actual evidence and unresolved qualifications

The archive preserves the earlier fourteen-case slice and 122-case combined
compatibility run separately from the later full-source verification
revision. The fixed 26f7c59 native17+policy12 run has 29 actual cases on each
of three runtimes/two SQLite versions, zero skip and unchanged measured input
hashes. Four corrupt-source cases require unchanged original SQL/financial
rows and generation zero with no native objects. The fixed install-interrupt
case executes actual DDL before failing and verifies rollback before retry.
The real prepare/acquire competition permits exactly one success.

Tests invoke the actual pinned 45818c0 batch-aware binary across base/batch
and prepared/unprepared combinations: prepared is rejected while old default
financial writes work. The pinned pre-fencing ad3 binary cannot post to a
prepared authority. Their archive hashes and license members match the
recorded provenance. This is local old-binary refusal evidence, not malicious
OS-owner protection, external anti-rollback, replica fencing or HA consensus.

[Independent static checks](../evidence/runs/credit-native-independent-review/static-checks.json)
verify syntax, the empty trading-format set, source-validation-before-DDL
ordering, unchanged route/storage/credit source, old fixture hashes/licenses
and three-runtime raw-log/source hashes. The independent financial policy
reference and the separate artifact review remain distinct deliverables; this
review does not sign their numerical or loaded-code identity conclusions.

Full combined-source local/CI/package acceptance is still required. Positive
intent enforcement, typed actual operation context, complete source/audit/
replay, global budget governance, customer borrowing permission and financial
sign-off remain future gates. No microtest or this static review makes the
system a qualified lending or exchange production platform.
