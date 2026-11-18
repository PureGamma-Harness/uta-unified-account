# Admission SQL4 once: fresh component verification proposal

Status: CODE_ONLY / NOT_RUN. The completed PURE7 RAW review
`05d060a44c47a3b59a0e527462b2cbb9084f73e8` supports only its prior pure scope.
It is not SQL evidence. This isolated preparation starts from source3f9dce8a;
all61 financial modules and both admission test files retain their be3c5c3
bytes. No target import, compilation, SQL/test execution, worker, native probe,
benchmark, CI or child agent was run to prepare this proposal.

## Fixed business scope and manual values

Four original methods from `test_decision_admission_capture.py` run directly,
failfast, without discovery. Each creates one fresh single-account authority.
There is exactly one declared local `apply_fill(.5,100)` call and zero Matcher
calls. This is an unpaired local component execution, not a complete trading
chain or confirmed paired-fill throughput. No credit, external custody,
cross-shard, writer-fencing/HA or real-funds qualification follows.

| case | ledger events | account version | orders / fills / audit decisions | final cash / reserve |
| --- | --- | --- | --- | --- |
| ordinary | 1 | 2 | 1 / 0 / 1 | USD10.04 /10.04; halted after original acceptance |
| MM equality | 1 | 1 | 0 / 0 / 0 | USD10.04; fee0.04 would leave equity=MM10, so reject |
| configured | 2 | 4 | 2 / 1 / 3 | USD99.98 /5.04; position0.5 cost50 |
| coexist | 1 | 1 | 0 / 0 / 0 | USD10.04; two policy candidates must reject inference |

USD scale is2 except the equality case's8; configured also has BTC scale8.
Mark/limit100, IM0.1, MM0.05 (equality case0.1), multiplier1 and fee0.0004
are the original examples. Configured fill50 notional charges0.02, posts
customer-0.02/system:fees+0.02 and realizes0 PnL. Its remaining ordinary
reserve is5.02; RO close0.5 adds0.02, giving risk equity99.98, IM5, MM2.5,
available89.94. That RO full projection removes the position, costs0.02 and
retains the original order reserve5.02, giving equity99.96/available94.94.

The explicit JSON oracle records native postings, deposit/fill business-key
algorithm, complete balances/order/position/decision inventories and version
steps. Five journal events and four decisions are proposed aggregate counts,
not observed results. Known-order retry occurs once in the original ordinary
method; expected no extra order/decision/event. Source-argument ambiguity is
rejected once in the original coexist method and once during post-verification.
Detached-record negative groups and RO guard checks are separate from the four
unittest IDs and are not new committed trades or fills.

## Unchanged test bytes and explicit resource adapter

The original fixture uses `TemporaryDirectory` and registers its cleanup, which
would erase the original database. The harness changes only that test module's
`tempfile` reference to a fixed-directory adapter and records each fixture
return. It does not patch the process-wide tempfile module, sqlite3.connect,
financial methods, schema definitions, fee/risk policy or four test bodies.
The four original cleanup callbacks execute, but the adapter retains rather
than deletes those four directories for evidence. This declared cleanup-
retention difference is not a proof of standard TemporaryDirectory deletion.

Exact families are `inner/cases/{ordinary,mm-equality,configured,coexist}/`
`admission.sqlite3` and each file's `-wal`, `-shm`, `-journal`. Fresh publication
may use only empty `.uta-create-*` files in the same four directories. Extra,
repeated or reordered fixtures fail; the original method sequence is fixed.
Full-module FrozenUTA/FrozenLoader loading preserves all source annotations,
properties and function semantics; no selected financial AST is constructed.

## Actual handles and read-only verification

The entry derives capture/helpers/whole-module loader from funding SQL once
source2326106b and adapts only this declared scope. Its audit hook observes
real SQLite connection URIs and native handle events; it appends handles
without inspecting them before their native initialization finishes. Only the
exact four families' rw/ro URIs are allowed. The hook never returns fake
connections or patches connect. A positive result requires all observed
handles already closed before new RO verification and after it, before any
leak cleanup. Cleaning a leak never restores qualification.

Post-verification opens real new `Database.read_transaction` connections,
requires query_only1, and constructs ExchangeService with `_existing_connection`
to use existing schema/current policy/current artifact verification without
CREATE/repair. It checks ledger replay and each native posting, full nonzero
cash inventory, position cost, order state/version, actual local fill/audit
links, market/rule/source bindings and historical decision replay.

For coexist, `_source_arguments` must still reject exactly the ambiguous
candidates. The separate read join uses explicitly known original constructor
arguments and the exact current stored artifact; it does not claim automatic
source reconstruction or full `open_existing_services` acceptance. No old
policy is removed, rewritten or deduplicated and no compatible-math bypass is
added. Migration of an existing authority remains unsupported.

Each actual accepted record is additionally checked using detached copies
with consistent corrupt pre/post halt types, missing admission evidence and
an altered projected fee. No archived row is modified. A separate real RO
transaction attempts control DML, must deny it and poison its commit; schema/
row digest and main database bytes must remain unchanged. A failure stops
post-SQL verification immediately; the harness does not repair or retry it.
Raw actual economic rows, decisions/replays and a deduplicated actual artifact
are retained privately so independent RAW review need not trust booleans alone.

Risk/reserve numbers still use `_replay_state` and the original production
numerical engine. Settlement/admission predicates have a separate derivation,
and the stated constants are manual; this is not an independent Cross model.

## Resources, caller and evidence

Proposed limits: CPU1; OS target30s plus5s target/drain classification; shared
target raw256KiB including512B failure trailer; logical control8MiB. Four
database families reserve64MiB logically (4families x4names x4MiB/file) plus
empty publication temps. RLIMIT_FSIZE4MiB is per file, not an aggregate hard
quota. Disk observations occur at real connection events and checkpoints, not
continuously inside every native SQLite write. No warm measurement was run.

The concrete SQL4 caller is adapted from the already reviewed sticky-timeliness
PURE7 caller. It separately binds final actual HEAD, plans, complete retained
inputs and its control pin, gates only its new owned outer, records actual
wait/reap/EOF and checks BEGIN/intent/END, exact SQL paths/final file hashes,
closed native handles and original source after. Its outer wait proposal is60s
with unchanged2s reap/.2s drain; late normal EOF cannot restore qualification.
It does not infer its own future exit from CALLER_END or certify descendant
reap after a timeout. Preparation/fsync native blocking is not a Python hard
wall-time guarantee. Root must observe actual caller exit/end independently.

All DBs/sidecars, full retained capsules, manifests, actual process bindings
and archives stay private. Public output is limited to reviewed finite
synthetic projections, allowed raw fields and opaque hashes. Any first FAIL
or UNKNOWN stops this scope and preserves originals, with no refresh/retry.
Fixed budgets/paths and all source inputs must be sealed and independently
reviewed before root issues a separate exact execution GO.

## Deployment and rollback

This adds validation tooling only. Operate exclusively on new synthetic
authorities, never a classic or live authority. No schema/product activation
or data migration is introduced. Rollback removes these new control files
while retaining prior PURE7 evidence, historical policies, orders, fills and
audit archives. Existing-authority handoff, full matching, financial crash
recovery, performance, HA and real-funds approval remain OPEN/NO_GO.
