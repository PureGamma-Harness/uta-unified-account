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
