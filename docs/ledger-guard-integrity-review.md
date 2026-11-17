# Independent ledger guard integrity review

At source `5d0f34acba48e59f59650013b190edf8a72faa8e`, a deliberately weakened
`ledger_postings_no_update` trigger is accepted by public ledger verification,
ledger reopening and managed take-over. One real synthetic funding post remains
unchanged throughout. This is a detection failure for trusted-owner offline
schema damage, not an untrusted customer operation or a writer-lease bypass.

## Trace and boundary

`DurableLedger.__init__` executes the schema's `CREATE TRIGGER IF NOT EXISTS`
statements before validating the stored version and scales. An existing same
name therefore leaves its original stored SQL untouched.
`DurableLedger.verify` performs integrity/FK checks, validates version/scales,
then checks only that seven expected trigger **names** occur in `sqlite_master`.
It does not bind those names to a table or inspect their SQL. Journal replay
still independently validates event sequence, seal, fingerprints, hashes,
per-asset balancing and materialized balances.

The seven native guards are `ledger_events_no_delete`,
`ledger_events_seal_only`, `ledger_postings_no_update`,
`ledger_postings_no_delete`, `ledger_postings_unsealed_only`,
`ledger_assets_no_update` and `ledger_assets_no_delete`. The one behavioral probe
below exercises only the posting-update guard; the shared name-only inventory
check is the static evidence for the wider inspection gap.

The writer fence has separate exact table/SQL comparisons for its control
objects and for the `writer_fence_data_*` triggers. Those data triggers assert
the current writer lease on I/U/D; they do not establish the native ledger
trigger's journal-immutability semantics. The new Spot exact definitions cover
its four receipt/fill guards, not these seven ledger guards. The service startup
does call `ledger.verify`, so the name-only check is reused during reopening.

Managed take-over first preflights Spot footprints, then prepares its manifest,
enables shard fencing and opens the owned exchange. A source without a Spot
footprint does not receive an independent ledger-guard preflight at that first
stage. A repair should reject damaged ledger guards before irreversible fencing,
as well as during public ledger verification/reopening. Merely detecting them
in the later owned-service constructor can leave a partially fenced authority.

## Actual bounded probe

The independent case is
`tests/test_ledger_guard_integrity_review.py`. It creates one halted, single-shard
synthetic source through public router APIs, creates Alice, and deposits 10 USD.
The resulting one double-entry post has customer `1000` and custody `-1000`
minor units. The initial `verify()` returns 1.

The original immutable trigger actually rejects an UPDATE. The offline fault
then replaces only its SQL with the same trigger name/table/action plus
`WHEN 0`. A savepoint probe changes one existing posting's units from `1000` to
`1001`, confirms the changed value, and rolls it back. Only the disabled guard
is committed. No posting, event, hash, balance, account or prior source row is
changed by this injection.

Observed after that rollback:

| Public operation / invariant | Actual result |
| --- | --- |
| Existing ledger `verify()` | Returns 1; no error |
| New `DurableLedger(...).verify()` | Returns 1; no error |
| `DurableProcessRouter.take_over(...)` | Returns successfully |
| Take-over manifest / fence | `initialized=1`, `managed=true` |
| Damaged guard SQL | Preserved with `WHEN 0` |
| Original source rows / ledger history | Unchanged |
| Worker processes started | 0 |

The one-case run is pinned to one available CPU and fails the intended
rejection assertion in 0.133 seconds. Its raw stdout records all observations
before the assertion; raw stderr preserves the actual failure. This review
changes no runtime source and claims no green fix, production qualification,
capacity result, or real-funds approval.

The [evidence directory](../evidence/runs/ledger-guard-integrity-review/README.md)
contains the command, source/runtime hashes, machine-readable observation and
unmodified red logs. A fresh run uses a disposable temporary source and starts
no managed workers. The trusted OS/database owner remains outside the customer
threat boundary described by the storage module.

## Integration correction and pending full validation

`DurableLedger` now derives the seven official protection definitions from the
same fixed `_SCHEMA` used for installation, accounting for SQLite removing
`IF NOT EXISTS` in stored trigger SQL. Verification checks name, object type,
table and exact SQL. Reopening an existing ledger validates these protections
before any schema-install statement, so missing or weakened guards remain
unchanged evidence rather than being implicitly repaired. A fresh empty ledger
still installs the original definitions; financial units and journal format are
unchanged.

Offline managed initialization/takeover additionally performs complete read-only
journal verification on **all shards before any manifest, queue or fence**.
This uses verification-only views without invoking financial constructors.
Corruption raises `503 ledger_corrupt`; it does not release funds or reconstruct
history. A later post-preflight quiescence violation still follows the existing
HALTED/incomplete forward-recovery rule. Full historical replay is deliberately
kept out of the normal market-activation path; this change does not introduce an
online full-journal scan at each quote.

The first integrated 73-case regression found one existing fixture relying on
constructor repair after deliberately dropping a guard. Its original error log
is retained. The fixture now requires reopening to reject and preserve the
missing guard, then explicitly reinstalls its captured original SQL before the
existing hash-corruption assertion. The journal/hash assertion is unchanged.
The original independent red case, three additional all-shard/read-only cases,
storage, migration and spot/strict-JSON/guard regressions then passed **76 tests
in 13.518s** on Python 3.12.14 / SQLite 3.53.1. This is targeted evidence;
independent recheck, full-source matrix, package verification and long-run
qualification remain pending. Production remains **NO-GO**.

Deploy a fixed new artifact while source writers are stopped and preserve every
source file and business ID on rejection. Restoration of a damaged definition or
history requires a separately reviewed offline recovery; this runtime refuses
automatic repair. Code rollback must not be used to bypass rejection with an
older permissive verifier or to downgrade managed guards.

## Independent Python 3.13 / older SQLite check

The exact correction source `74e3ec9b06b7cbd55fbb145c1984e76f9dbcaac4` was
independently reviewed in a new detached worktree. On system Python 3.13.5 /
SQLite 3.46.1, the unchanged original regression, three all-shard/read-only
preflight cases and thirteen storage cases passed **17/17 in 1.094s**, pinned to
one available CPU, without skips. The original damaged-guard case now records
`LedgerError` from verify/reopen and `503 ledger_corrupt` from take-over, with
no manifest or managed fence. Its damaged SQL and every original financial/source
row remain unchanged; its financial-history digest matches the original red run.

Independent static review found no blocking issue in the minimal correction.
The seven official definitions and unsupported-version contract are retained;
replay remains on the offline paths. A read-only AST comparison also found all
seven licensed legacy fixture definitions identical to the expected stored
definitions. Exact SQL matching conservatively rejects operator-rewritten
equivalent SQL, and offline quiescence is still required. These checks do not
prove arbitrary future legacy schemas or concurrent offline owner edits.

The [independent raw records](../evidence/runs/ledger-guard-integrity-review/independent-74e3ec9/README.md)
bind the 17-case result to source/test hashes and preserve the earlier red and
fixture-error records. No runtime/test source was changed by this independent
review. Full matrix, packaging and long-run qualification are separate gates;
production remains **NO-GO**.
