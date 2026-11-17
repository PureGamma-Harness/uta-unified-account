# Credit authority code upgrade and recovery protocol — proposal / NO-GO

This is a design contract, not an implementation or an approval. It is based on
`3f5eb0e38ee43bc7ee4a16d3d5ecef6a965380ac`. No installer, loader, schema,
financial service, existing database or production permission changes here.
PR19 remains Draft / overall NO-GO. The pure model checks a bounded protocol
under stated assumptions; it does not establish SQLite, process, host or
real-funds acceptance. This is this system's proposed policy, not a claim of
alignment with Bybit, Binance or another exchange.

The selected strategy is a stopped, verified **successor authority** with an
append-only epoch lineage. The old authority becomes permanently read-only
before a successor can write. An existing V2 database is never opened for
financial writes by an unknown build. No format3, extra artifact row or relaxed
verifier is introduced to get around current immutable tables.

## Why a deployment needs a protocol

The current implementation provides these relevant constraints:

* `uta/credit_native_v2.py:load_marker` compares the actual complete loaded
  code/runtime artifact, exact envelope/configuration, exactly one retained
  artifact, stored risk policy, allocations and compiled SQL. A changed source
  or runtime cannot use the old capability. This also blocks a changed build's
  normal existing-only read factory; a new reader is not implicitly trusted.
* `uta/writer_fence.py:_load` checks the canonical path and exact inventory.
  `_assert_token` binds authority, generation, PID, boot identity and local
  CLOCK_BOOTTIME expiry. `BEGIN IMMEDIATE` serializes a database's writer;
  triggers and `before_commit` recheck actual permissions. It is a single-host
  lease, not a fence shared by two databases, a replica election or protection
  against a trusted OS/database owner.
* Source plus `PENDING` share the original producer COMMIT. A later financial
  COMMIT closes intent, financial effects, four/seven actual journal legs,
  audit when applicable, receipt and `SUCCEEDED`. A failed financial transaction
  leaves the original accepted source and `PENDING`; it does not undo acceptance.
* `credit_audit_v2_replay` requires the original code/runtime and original
  historical market/checkpoints/rules. It does not import executable archive
  names or substitute today's code, account, clock or market.
* Generic readiness remains false and public/CLI new managed borrowing remains
  501. The scoped existing after-COMMIT/reply-loss, real-UTC and old-binary
  observations are in `credit-v2-draft-milestone.md` and its linked reports.
  They do not prove upgrade, mid-COMMIT crash or production readiness.

Current APIs cannot install a retirement barrier, publish a successor or accept
an imported opening segment. Current fresh-only installation is not a migration
tool. Every new component named below is a prerequisite for a separately
reviewed implementation, not a way to operate PR19 today.

## Choices and selection

| Choice | Safety and operational consequence | Decision |
| --- | --- | --- |
| Retain the exact old artifact/runtime | Original-CID recovery works without a code migration; all original dependencies must remain available | Default recovery for today's published V2 |
| Change V2 artifact/config/marker or add an accepted-build list in place | Contradicts exact immutable capability semantics; can reinterpret old decisions and let stale writers return | Rejected |
| Introduce an epoch-aware in-place protocol | Requires a new audited capability, old-build retirement, compatibility reader and crash-safe migration of one live file; current V2 cannot provide it | Possible future alternative, outside this proposal |
| Seal old authority, verify complete state, activate a successor segment | Keeps old data/artifacts byte-for-byte, permits explicit code/rule lineage, and has an unavoidable availability gap while neither side writes | Selected for first implementation |

Successor activation preserves the logical lending domain and shard. It uses a
new physical authority ID and canonical path, and a monotonic domain epoch.
Domain identity and original `(account, CID, kind, payload_hash, source_id)`
remain stable. Epoch must never be added to the business deduplication key in a
way that permits an old CID to execute again. Query searches the authenticated
lineage and returns the original exact receipt, including pre-V2 gaps; it does
not backfill a decision or fabricate a replacement CID.

## Required control plane and trust boundary

An independently reviewed handoff coordinator owns a durable, append-only
domain registry and a compare-and-swap active-epoch pointer. Registry records
bind the domain, predecessor, successor, root manifest, artifact and policy IDs,
handoff certificate, approvals, state, unique request ID and prior record hash.
Conflicting records for the same request, predecessor or claim are fatal.
Append-only denial/abort records preserve failed attempts; they grant no lease.
The pointer may advance only to a unique approved child of its current epoch.
This registry is not a financial ledger and cannot mint pool capital or cancel
a debt. Availability loss of the coordinator fails closed for new writes.

The coordinator must provide a persistent intake barrier, permit accounting and
a single authorized executor. It stops **all** source adapters, not merely new
BORROW admission or market publication. Account halt does not stop REPAY or
producer intake. An accepted source transaction holds a counted intake permit
until its actual outcome is resolved. Barrier completion requires all earlier
permits to have definite outcomes. The barrier is durable across process and
host restart; an in-memory flag, paused UI, chmod alone or expired lease is
insufficient. An exact old-runtime drain executor may process already accepted
commands while intake stays barred. No generic service objects are rebound.

Existing V2 binaries do not know this coordinator. A future deployment must
constrain the exact old producer/executor through an independently reviewed
host/access broker during draining, and demonstrate that no alternate authorized
producer path can bypass its barrier. If that cannot be established, stop all
processes first; any unresolved accepted command prevents migration. It is not
safe to pretend the current source UDF checks an external epoch.

Permanent retirement requires a new, independently reviewed, offline metadata
operation, absent today. Its design is an **append-only terminal tombstone** in
a reserved `writer_fence_` inventory, bound to the final root and intended child.
It must invalidate/revoke old ownership and make every supported actual old
binary refuse acquisition, renewal, producer and financial writes on restart.
It must not update/delete the V2 capability, configuration, old intents, original
audit, allocation or receipts. The normal old `Database` transaction cannot
install this unknown inventory: its current before-COMMIT catalog check would
reject it. A future retirement mechanism therefore needs its own narrow audited
metadata authority, exact allowed delta and actual transactional tests; this
document supplies no raw SQL bypass recipe. It changes no financial row.

The old canonical database is then retained with read-only host policy, revoked
service access and retained exact original files/runtime. The tombstone is the
durable old-binary refusal; host isolation is an additional boundary. Registry
CAS alone does not stop an old writer against another file. Conversely, an old
binary refusing a successor's unknown schema does not stop it reopening the
original file. Both paths must be tested. A trusted host owner can subvert
SQLite guards; trusted operators, immutable deployment media, storage and the
coordinator are explicit assumptions, not cryptographic attestations.

Retirement also survives storage rollback: the registry retains the terminal
predecessor ID/root independently of that database. A host/access broker must
refuse launching any old writer or mounting a pre-retirement backup writable
for an already retired domain, even if that backup lacks the tombstone. Loss
of this anti-rollback evidence means no writer can start. Test an old primary
returning with both current storage and a stale snapshot; local generation
monotonicity alone cannot fence the latter.

## State machine and commit boundaries

All transitions are idempotent by handoff request ID and exact bound hashes.
Repeating an identical committed transition returns its original record; a
different root/build/child with that ID is a conflict. Responses and advisory
checkpoints never prove a COMMIT. Recovery independently reads authoritative
rows, registry and tombstone before taking the next transition.

| State | Permitted activity | Next state and required durable evidence |
| --- | --- | --- |
| `ACTIVE(e)` | Only approved artifact/rules at e; source intake and financial execution require current permits and a live local token | `QUIESCING(e)` after the intake barrier is durable; pre-barrier in-flight permit outcomes still need resolution |
| `QUIESCING(e)` | No new sources; exact old executor may deliver/reconcile already accepted sources and drain original CIDs in FIFO | `FROZEN(e)` only after all permits, source delivery, PENDING, financial/funding/interest work and unknown outcomes are zero; stop executor, release or expire lease and invalidate all handles |
| `FROZEN(e)` | No source or financial writes; exact old exporter and independent raw read-only auditor build/recompute a complete consistent root | `PREPARED(e+1)` after root, candidate opening, actual build/runtime, code/rule compatibility and independent approvals match |
| `PREPARED(e+1)` | Candidate has no producer/financial permission; its opening state is provisional and replayable | `RETIRED(e)` after atomic old retirement/tombstone is confirmed, final root remains identical and coordinator records that proof |
| `RETIRED(e)` | Old cannot resume; successor still cannot write; interruption causes downtime | `ACTIVE(e+1)` after handoff certificate is consumed once and registry CAS e→e+1 commits, then a fresh successor token is acquired and new service objects are constructed |
| `ACTIVE(e+1)` | Only the approved successor can accept/execute; old CIDs return original receipts without effects | `HALTED(e+1)` on uncertain data, permit, code, rule, storage or reconciliation state; recover at e+1 or advance through a new reviewed handoff |
| `ABORTED` before old retirement | Candidate remains ungrantable; append the exact abort result and revoke all candidate credentials | Explicit old resumption may obtain a fresh generation under the same original artifact after revalidation; intake reopens last |

Before retirement, any difference between the export root and a newly recomputed
old state aborts preparation and requires a fresh drain/export/approval. A
post-export financial COMMIT or unresolved CID cannot be hidden by incrementing
a watermark. After retirement there is no unretire or pointer rewind, even if
no new financial operation has committed. A rollback then is another forward
handoff with independent approval. Once new effects exist, its opening state
must include them; returning to an older database snapshot would erase debt or
duplicate funds. A reviewed older code artifact can be selected in a later epoch
only if it supports the actual current state/rules through the new migration
contract. Its old binary is never simply re-enabled against its retired file.

The retirement COMMIT, registry activation COMMIT and successor financial
COMMIT are distinct. Order is old-retired → certificate/CAS → successor-token
→ financial writes. This deliberately favors a no-writer interval over overlap.
A failed prepare/retirement transaction leaves either all or none of its own
metadata delta. If its COMMIT result is unknown, query it; do not assume rollback
or create another child. An active successor that fails before financial COMMIT
rolls back all intent/effect/audit/receipt/terminal rows in that transaction,
retains original accepted source/PENDING, and remains responsible for that CID.
An after-COMMIT lost reply returns the original terminal receipt on query/retry.

A write permit is pinned to its domain epoch, actual artifact/policy and
transaction identity. It remains outstanding across a lost reply or expired
process lease until independent original-CID reconciliation determines the
transaction outcome. The coordinator may not recycle it merely because a timer
elapsed. Cutover cannot overtake a still-outstanding producer or financial
permit. Actual before-COMMIT loaded-code/lease/effect checks remain necessary;
an earlier permit is not a substitute for them.

## Drain and cross-database source reconciliation

Today's producer source and PENDING are one COMMIT on the same authority;
financial completion is a second COMMIT. The protocol must retain those two
boundaries. A future source database plus financial database adds a delivery
boundary, not a distributed atomic transaction. No XA, replication consistency
or exactly-once transport is assumed.

1. Persist the intake barrier and enumerate every accepted CID/source through
   its exact sequence/watermark, plus all pre-barrier outstanding permits.
   Query each unknown producer outcome at its original database/key.
2. Join original source, financial inbox, native intent/decision, actual sealed
   journal, credit receipt and terminal result in both directions. Verify
   original bytes, account, kind, amount, authority/domain and payload hash.
   `source-only` means delivery remains due; a missing terminal is not rejection.
3. Deliver source-only entries idempotently under original IDs, drain original
   FIFO with the old runtime, and requery every unknown financial outcome. A
   known business rejection is terminal only after its actual durable receipt;
   technical failure, absent reply or elapsed TTL is not a rejection.
4. Require all accepted sources to have one exact terminal result and no open
   intents, pending rows, orphan effects or undelivered entries at both cutoffs.
   UNKNOWN never releases allocation, returns funds, reissues a source, moves
   to another shard or becomes a new CID. Do not clear/drop/cancel a PENDING to
   make the upgrade finish. If the old exact runtime cannot finish, stay
   unavailable and recover it; unresolved-command transfer is a separate,
   unapproved migration protocol.

All involved databases must be quiescent before snapshots are combined. Each
consistent per-database snapshot records its own cutoff, schema, storage
identity and transaction boundary; the join proves the cross-database cut.
Independent snapshots taken while producers still run are not a global cut.
No claimed physical-COMMIT UTC time is invented. A source database cannot be
reopened at a prior sequence after successor intake starts. A later discovered
pre-barrier source or terminal mismatch halts the domain and triggers incident
reconciliation; it is never silently replayed into the successor.

## Complete snapshot and continuation contract

The private root manifest is canonical and content-addressed. It includes the
handoff request, domain/shard/epoch, old authority/canonical path, exact database
and storage identities, consistent SQLite backup/WAL inclusion procedure,
per-database cutoffs, table schemas/indexes/triggers, complete declared table
inventory, row counts, sorted full-row content roots and explicit audit gaps.
Copying only the main file while WAL can contain committed state is invalid.
Never expose original databases, tokens, nonces or credentials as public evidence.
Lease generations and ownership observations are retained without secrets.

Full state is verified, not a USD net equity or a list of accounts that borrowed:

| Group | Required exact content and reconciliation |
| --- | --- |
| Asset/catalog | Every declared asset, scale, supported range, product/catalog/rule versions; zero rows and unsupported nonzero assets are explicit; unknown assets deny import |
| Financial accounts | Per account/asset gross cash, cash deficits, principal, interest, receivables, interest cash, freezes, reserves, versions, mode/halt/liquidation state; complete orders, fills, positions, funding/fee obligations and other original financial state |
| Loans/pool/budgets | Each original loan/claim and repayment component, full pool balance and funding claims, original global/shard allocation certificate, outstanding gross P/I, budget usage and unreleased UNKNOWN claims; no netting P against I or pool |
| Ledger | All events, exact ordered legs, per-asset balance checks, canonical hashes, first/last sequence, prior/final head and complete original chain; verify account/credit materialization from those events |
| Business history | Every original source/CID/payload/receipt/terminal, intent, decision and archive reference; byte-preserved no-native history and declared gaps; full counts and no duplicate/orphan identities |
| Executable history | Actual source/loaded-function/runtime artifact, fixed dependency list, Python/SQLite/OpenSSL, all historical code and rule documents, market SID bytes, scales, rounding, precision and UTC checkpoint policies |

The original exact runtime exports and replays original decisions read-only.
An independent raw read-only SQL/reference tool checks the same original
database and uses independently implemented exact integer/Fraction accounting;
it must not call the exporter or current financial engine as its oracle. Each
historical segment is replayed with its original code and original rule/data
versions. New code may perform a differential shadow computation; a mismatch
blocks activation rather than rewriting historical evidence. An archived
manifest does not authorize import/execution of arbitrary stored names. Old
executables run in an isolated reviewed environment, without financial write or
network credentials. Missing exact runtime, missing archive or incomplete
dependency identity is an unavailable replay, not a verified result.

Export canonical replay bundles **before** retirement while the original exact
factory can still verify its supported inventory at its canonical path. After
the terminal tombstone, that old factory must refuse the retired original too.
Historical bundle replay then runs the exact old standalone replay engine on
retained bytes; a separately reviewed, query-only tombstone-aware reader checks
them against original rows. This reader cannot acquire a lease or execute
business work and does not pretend the old factory accepted new inventory. A
copied snapshot cannot simply be handed to the old factory: canonical-path
checks still apply. Any namespace-based backup verification must preserve the
recorded canonical path in a read-only isolated environment without service or
write credentials, and needs its own actual acceptance.

The successor opening is a new **migration segment**, not a synthetic borrow,
repay, deposit, funding event or historical decision. Its opening vector must
equal the old close per account, loan, claim, asset and component, without
rounding, fee/interest accrual, limit expansion or changing ownership. A segment
genesis commits the old final ledger head and full root, records a new segment
identity, and preserves original event/CID namespacing. Global history verifies
the predecessor segment before continuing the new segment; a new local sequence
must never be presented as uninterrupted original ledger history. Current
financial-source verification has no such opening-segment support. A future
storage/reader/verification contract must implement it explicitly before this
option is executable.

A non-reusable handoff certificate maps the old allocation/funding-claim set to
the successor epoch with identical gross state and limits. The global registry
atomically consumes its predecessor ownership once. Old and successor count as
one continuous claim during preparation, never two reusable allocations.
Old funding receipts are lineage, not new pool contributions. Independent
allocator review must prove that concurrent shard handoffs cannot duplicate,
recycle or enlarge a global claim. Rule changes, asset scale changes, interest
policies and capital additions require separate explicit policy migrations;
they are not smuggled into a binary-only upgrade.

An approval record binds the old root/head, new actual artifact/runtime, new
policy IDs, reviewed migration executable, exact compatibility report, successor
opening root, handoff certificate, expiry/conditions and reviewer identities.
New artifacts and approvals are appended to the new lineage, never substituted
under an old ID. Content hashes identify bytes; they are not approval signatures.
Unknown builds, extra policies, altered roots or approval expiry deny activation
and every attempted write. An actual loaded-code mutation must fail closed.

For a future implementation, the review packet has these mandatory object
shapes. These are proposed external document schemas, not native capability
formats. Canonical encoding requires sorted object keys, exact integers/native
unit strings, explicit nulls, deterministic array order and duplicate/unknown
field refusal. Signature verification, key governance and durable storage still
need an independently reviewed implementation.

| Proposed object | Required fields |
| --- | --- |
| `UpgradeManifestV1` | `document_kind`, `request_id`, `domain_id`, `shard_id`, `predecessor_epoch`, `predecessor_authority_id`, `predecessor_registry_record_id`, `database_cuts`, `old_artifact_ids`, `old_policy_ids`, `old_state_root`, `old_ledger_heads`, `source_terminal_root`, `allocation_claim_root`, `declared_gaps`, `successor_epoch`, `successor_authority_id`, `successor_canonical_path`, `new_artifact_id`, `new_policy_ids`, `migration_artifact_id`, `opening_root`, `compatibility_report_id` |
| Each `database_cuts` member | `database_role`, `authority_id`, `canonical_path`, `storage_identity`, `schema_root`, `full_table_roots`, `full_row_counts`, `source_cutoff`, `inbox_cutoff`, `ledger_sequence`, `ledger_head`, `snapshot_content_id`, `snapshot_method_id`, `intake_barrier_record_id`, `outstanding_permits` (must be zero) |
| `HandoffCertificateV1` | `document_kind`, `domain_id`, `shard_id`, `request_id`, `manifest_id`, `predecessor_epoch`, `successor_epoch`, `old_allocation_ids`, `funding_claim_root`, `gross_component_root`, `unchanged_limits_root`, `global_allocator_record_id`, `single_consumption_key` |
| `ApprovalV1` | `document_kind`, `manifest_id`, `certificate_id`, `reviewer_identity`, `reviewer_role`, `review_report_id`, `decision`, `valid_from`, `expires_at`, `conditions`, `signature_key_id`, `signature` |
| `LineageRecordV1` | `document_kind`, `domain_id`, `registry_sequence`, `prior_record_id`, `request_id`, `transition_kind`, `from_epoch`, `to_epoch`, `manifest_id`, `certificate_id`, `approval_ids`, `retirement_proof_id`, `transition_result` |

Content IDs cover the entire unsigned object using domain-separated hashes;
signature envelopes bind those IDs and role/expiry. Neither manifest nor
certificate contains its own content ID. The manifest also excludes the later
certificate ID to avoid a hash cycle: certificate binds the completed manifest;
approvals and lineage bind both. `transition_kind` is one of barrier, freeze,
prepare, retire-confirmed, activate, abort or halt; every kind has exactly one
permitted predecessor state. Null fields must be declared per transition rather
than omitted to bypass a proof. Snapshot cutoffs include complete row roots,
not only MAX(sequence). A single-consumption key names the domain/predecessor/
claim set, so a second request ID cannot consume the same ownership again.
Approvals require independent financial and operational roles; the author of
the new build/model cannot satisfy those roles alone. Raw UTC observations do
not assert physical-COMMIT timestamps.

## Acceptance gates and bounded model

`scripts/model_credit_authority_upgrade.py` is a standalone, database-free model.
It explores two CIDs, two assets, two epochs, single staged financial work,
atomic source+PENDING or split source delivery, lease loss/recovery, quiescing,
prepare, retirement, activation and abort. It checks no stale/unknown writer,
no double effect, per-asset journal balance, interest-first repayment, exact
opening, original-CID receipts, once-only handoff and rollback boundaries. Its
negative controls must find intentionally omitted fencing and root checks.
It does not model a malicious operator, SQL/UDF catalogs, actual timers,
signatures, WAL/power loss, arbitrary concurrency, larger states or live money.

The retained run at 2026-11-17 15:36:44.987150–15:36:45.055608 UTC passed on
CPU3/Python3.12 with an external 3s watchdog: 298 states, 648 transitions, all
seven bounded phases and 19 golden checks, including two invariant-failing
mutants. Model CPU was 0.007945s; wrapper wall time was 0.068464s. Exact script
hash, runtime, command, stdout/stderr hashes and raw result are retained in
`credit-authority-upgrade-model-result.json`. The preliminary pre-mutation run
is not claimed as retained final evidence. Reproduce the final script with:

```sh
timeout 3s taskset -c 3 python3 -W error::ResourceWarning scripts/model_credit_authority_upgrade.py
```

The implementation acceptance suite must retain independently reviewed golden
cases for at least:

* Real producer COMMIT crash before delivery; financial failure before COMMIT;
  actual mid/after-COMMIT process loss; original-CID status query in each case.
* Actual intake race at the barrier, source-only in another DB, duplicate and
  changed-payload delivery, orphan reverse joins, missing/UNKNOWN CID and FIFO.
* Complete multi-asset snapshot with nonzero USD deficits, principal/interest,
  receivables/interestcash, pool, opening exposures, zeros, gap history and an
  unsupported asset; tamper each component, cutoff, source and ledger head.
* Export then old financial COMMIT, wrong root import, prepare crash, retirement
  rollback and unknown COMMIT, crash after retirement/before CAS and after CAS
  before lease, duplicate handoff and concurrent child/shard attempts.
* Real old-source positive controls and actual old binary acquisition, renewal,
  source insertion and financial write refusals on **both** retired original and
  successor paths; stale PID, boot, token and an old primary returning after
  takeover. No permission callback substitutes for actual guards.
* Original historical code/rules replay; changed runtime/default/closure/code,
  unknown artifact, altered policy/SID, missing old runtime and signed-but-wrong
  root rejection. New-build read access must be explicitly reviewed as well.
* Exact original four-leg borrow and four/seven-leg interest-first repayment;
  post-upgrade reply loss; original pre-upgrade CID replay; post-new-effect
  downgrade refusal; forward rollback preserving every new committed effect.

Real-funds release requires a separately frozen implementation SHA, complete
supported-runtime/package/CI verification, independent financial and original-SQL
review, independent security/operational review, trusted-operator authorization,
production financial approval and demonstrated disaster/backup recovery. The
author of this proposal or model cannot self-sign these gates. There is no
production GO, real exchange alignment, HMAC/public enablement or throughput
claim in this deliverable. Operational decisions are in
`credit-authority-upgrade-runbook.md`.
