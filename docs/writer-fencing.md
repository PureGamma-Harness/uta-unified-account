# Managed single-host financial writers

`WriterFence` adds a persistent lease and monotonic generation to a local SQLite
financial authority. Enabling it changes the authority's write policy. The
existing unmanaged default remains available for existing reference workflows;
managed mode has no online disable or lease-bypass option. This module is not a
replicated lease, cross-AZ ownership service, custody control, or production
acceptance claim. The filesystem and service OS user remain trusted.

## Bootstrap and storage interface

Bootstrap and verify all required account, ledger, credit, matching, and queue
schemas before enabling management. Pause producers and stop old writers during
this handover. Enabling takes SQLite `BEGIN IMMEDIATE`, so previously running
write transactions finish or roll back before activation commits. After that
commit, previously created ordinary `Database`, `ExchangeService`, credit,
matcher, and `DurableLedger` instances cannot write financial state.

```python
from uuid import uuid4
from uta.storage import Database
from uta.writer_fence import WriterFence
from uta.service import ExchangeService

base = Database("/private/account.sqlite3")
# Existing deployment bootstrap and reconciliation happen here, before enable.
fence = WriterFence(base)
fence.enable("exchange:shard-0001")  # stable immutable identity; idempotent
# Acquire inside the worker process, never in a parent before spawning it.
token = fence.acquire(uuid4().hex, ttl_seconds=30)
writer_database = base.for_writer(token)
exchange = ExchangeService(writer_database, {"USD": 8})
try:
    # Submit durable commands / execute the normal financial APIs.
    # Renew well before expiry, outside any financial transaction.
    token = fence.renew(token, ttl_seconds=30)
finally:
    fence.release(token)
```

`Database.for_writer(token)` makes a shallow clone; it never grants permission
to old services by mutating their database object. It preserves subclasses,
including router shard identity checks on financial transactions. The read-only
`writer_token` property exposes the frozen token. A token contains
`authority_id`, `owner_nonce`, `generation`, and `process_id`. It is diagnostic
state, not a bearer secret. Serializing and restoring it within the same process
preserves its value; another PID cannot use it. Every worker process must acquire
its own token after starting. A live lease is not stolen because its PID appears
dead; callers wait for expiry or use the live owner's explicit release.

There are four transaction roles:

| Entry point | Allowed behavior |
| --- | --- |
| `Database.transaction()` | On an unmanaged database, existing behavior. On a managed database, reads remain possible, but all financial DML/DDL and inbox terminal updates require the current token. |
| `Database.read_transaction()` | A consistent read snapshot with `query_only` and a write-denying authorizer; no lease is required. |
| `Database.inbox_transaction()` | Only create the fixed inbox schema and insert new queued commands/configuration. Financial tables, lease tables, terminal updates, and deletion are denied. |
| Internal `_fence_transaction()` | Lease/authority/audit control only. It grants no financial DML/DDL permission. Applications use `WriterFence` methods. |

The inbox schema consists of `uta_command_config`, `uta_command_inbox`, the two
pending indexes, and eight explicitly named integrity triggers. Producer
transactions cannot update or delete queue rows. Queue triggers must require
new commands to start PENDING, forbid INSERT OR REPLACE over existing IDs or
sequences, and protect immutable payload and terminal state. Worker terminal
updates use the same token-authorized financial transaction as the financial
changes. This module allows that schema's creation; it does not implement the
queue or claim that an arbitrary hand-written queue schema is valid.

`WriterFence(database).assert_writer(connection, token=None)` is available for a
worker to require managed mode explicitly inside its already begun financial
transaction. Omitting the token uses `database.writer_token`. This prevents an
unmanaged database with a fabricated bound token from being treated as a managed
worker. The ordinary guard still validates actual writes and the final commit.

## Persistent lease and transaction boundaries

Enabling writes `writer_fence_authority`, `writer_fence_lease`, and the append-only
`writer_fence_events`. Authority identity and its original canonical database
path are immutable. A complete copy opened at a different path fails closed with
`authority_path_conflict`; relocation requires an explicit offline recovery
design, which this module does not provide. Generation starts at zero
without an owner and increments on every successful acquisition. Renew and
release do not decrement or reuse generations. All control operations serialize
with the same SQLite write lock as financial transactions. Acquisition fails
with `lease_busy` while the current same-boot lease is live. A new owner cannot
commit a takeover in the middle of another financial write transaction.

Every financial `BEGIN IMMEDIATE` reads persistent management/lease state before
application statements execute. A SQLite transaction authorizer denies every
unauthorized DML/DDL, including statements from triggers, old cached service
instances, constructor schema writes, and direct ledger writes. Even a current
financial writer cannot edit/drop lease state or enable `writable_schema`.
Caller-controlled COMMIT/ROLLBACK, attached-database writes, and extension loading
are denied on guarded transactions. A denied statement poisons the transaction:
catching its SQLite error does not allow the caller to commit remaining changes.

Immediately before committing protected writes, the guard reloads the persistent
lease, validates authority, nonce, generation, PID, boot, and expiry, then advances
the durable clock high watermark in the same transaction. If a lease expires
during calculation, all order, reservation, position, cash, and queue terminal
writes roll back together. The success boundary remains the actual SQLite commit.
No pending queue receipt or renewed lease is a substitute for that commit.

`DurableLedger.post(connection=...)` must join a registered `Database`
transaction when the authority is managed. An arbitrary raw SQLite connection
cannot be supplied through this API to bypass the guard. A read-only transaction
can still supply its connection to ledger reads. Independently constructed
unmanaged `Database(path)` objects detect the persistent marker on each new
transaction; they cannot keep using permission cached before activation.
An object explicitly bound to a token never falls back to legacy write behavior
when the managed marker disappears; its writes fail with `fence_not_managed`.
An unbound legacy object cannot detect that all management history was removed
by an external same-path restore. Such restores remain prohibited.

A writer holding SQLite's lock can delay lease acquisition by another process.
Expiry stops its eventual commit; it does not interrupt Python execution or
force-release a database lock. Set TTL and command duration budgets accordingly,
renew between transactions, and bound shutdown/wait times in the process manager.
A paused worker that holds a transaction must resume or be terminated before
another writer can obtain the SQLite lock. This preserves exclusion and may
reduce availability.

## Clock and process model

Production defaults use Linux `CLOCK_BOOTTIME` nanoseconds and
`/proc/sys/kernel/random/boot_id`. BOOTTIME advances through suspend and is shared
by processes on this host. It does not depend on NTP or civil time. A different
boot identity invalidates old tokens; the next acquisition still increments the
persisted generation. `expires_ns <= now_ns` is expired, including equality.
`ttl_seconds` must be a finite numeric value in `.001..3600`; booleans are invalid.
TTL conversion is integer nanoseconds and is not a financial calculation.

The persistent `observed_ns` high watermark detects same-boot clock regression.
Lease acquire/renew/release and protected financial commits advance it. A
regression against the stored watermark, or within a financial transaction,
fails closed with `fence_clock_regressed`. Missing/invalid clock or boot identity
also fails closed. Read-only status reports the current clock and lease state;
it does not renew a lease or advance its clock watermark.

Tests may explicitly inject `Database(..., fence_clock_ns=callable,
fence_boot_id="test-boot")`. These inputs are trusted test infrastructure and
must be shared consistently between instances in one experiment. They are not
an operator mechanism for reviving expired leases. Production uses the defaults.

`status()` returns `managed`, `active`, `authority_id`, `canonical_path`, `generation`, `owner_nonce`,
`owner_pid`, `boot_id`, `expires_ns`, `observed_ns`, and `now_ns` for a managed
store; an unmanaged store returns `managed=False, active=False`. Nanosecond values
are boot-relative, not UTC timestamps. Acquire, renew, release, and activation
have persistent audit events; transaction commits also advance the high watermark.

## Errors, recovery, and rollback

`WriterFenceError` extends `StorageError` and carries `code`. Important codes:

- `writer_fenced`: missing/wrong authority, owner, generation, PID, or boot for a write;
- `lease_expired`: the current lease expired; renewal cannot resurrect it;
- `lease_busy`: another same-boot live owner holds the lease;
- `fence_not_managed`: an explicit worker assertion/acquire requires activation;
- `fence_corrupt`, `authority_conflict`, `fence_clock_regressed`, or clock/range errors;
- `unguarded_connection`: a raw connection cannot join managed ledger writes.

The storage guard is an application correctness boundary. The service OS owner
can execute arbitrary raw SQLite/Python, replace files, disable callbacks, alter
the host, or restore all state consistently. Such actions are outside the fault
model; this mechanism is not an external tamper seal. Restoring an older complete
backup can regress lease history without an external witness. Never restore a
live authority or copy it to a second active host. SQLite WAL/FULL retains only
its existing local durability semantics; no replication acknowledgment is added.

On process failure, stop the old worker, retain all database/WAL files, wait for
lease expiry, then acquire a new owner/generation inside the replacement process.
Reconcile durable commands by original IDs. Unknown financial outcomes still
require querying persisted receipts; leases do not turn a lost response into a
rejection. A forked child must not inherit a parent's financial token.

There is no supported online disable, forced generation reset, TTL override,
or bypass flag. To roll back application code while preserving managed data,
use a version that understands fencing and acquire a new lease normally. A
strict offline recovery must stop and fence all old processes, preserve the
complete database/WAL and generation history, validate authority and financial
replay, then restart under a new token. A pre-management code rollback cannot
write a managed database and is not an acceptable recovery procedure.

## Validation

```sh
python -m unittest discover -s tests -p 'test_writer_fence.py' -v
python -m unittest discover -s tests -p 'test_storage*.py' -v
```

The focused suite covers old service/credit/matcher/ledger writes, immutable
activation, read/control boundaries, expiry at COMMIT with full rollback, renew
and generation transitions, boot/PID boundaries, a raw-connection ledger bypass,
and two real processes competing or resuming after a takeover. Run the same
suite under Python 3.10 and the current interpreter; SQLite authorizer constants
use stable numeric fallbacks for symbols absent from Python 3.10. Independent
queue/process fault suites verify composition. These tests do not establish HA,
load capacity, RPO under disk loss, or availability-zone recovery.

## Persistent SQL guards and real old binaries

The first implementation's Python authorizer did not stop a process actually
running the pre-fencing `ad3f5b8` source. That process never loaded the new
`Database` guard and could still deposit, admit orders, post a journal, and match.
This failure was reproduced in a separate `python -I` process and is retained in
`tests/fixtures/legacy_fence_red_evidence.json`; the initial passing tests covered
old objects using the new storage module and did not establish old-binary safety.

New managed authorities additionally install persistent SQLite BEFORE INSERT,
UPDATE, and DELETE triggers on every financial table. Their names are
`writer_fence_data_<sha256(table-name)>_<i|u|d>`. Each requires the zero-argument
`uta_writer_fence_v1()` function to return 1. Only a valid token-bound financial
transaction registers that function. Its callback checks authority, generation,
owner, PID, boot, and current expiry against the persisted lease snapshot held
stable by BEGIN IMMEDIATE. The record is reloaded before COMMIT. A genuine old
binary has no such SQL function, so SQLite rejects its protected statements even
though that binary knows nothing about fencing. Wrapped SQLite exceptions remain
storage failures, and all financial changes roll back. The authorizer remains a
second layer for capability and schema boundaries.

`writer_fence_guard_config` records persistent `guard_format=1`, and
`writer_fence_guard_tables` records the exact table/action inventory. Every new
managed transaction validates existing guard names, target tables, and complete
SQL definitions against that inventory. A missing, renamed, weakened, or extra
guard fails with `fence_guard_corrupt`. Startup, `enable`, and `upgrade_guards`
do not recreate missing protection. Immutable activation/upgrade audit markers
also distinguish an old deployment from loss of both guard metadata tables.

A legitimate token-bound schema transaction may create additional financial
tables and insert their initial data atomically. Before COMMIT, the new tables
are registered and all three guards installed. Existing guards must still match;
this path never repairs existing tables. No other connection can observe the new
financial tables before their guards commit with them. Existing ADD COLUMN
migrations may proceed if existing trigger definitions remain valid. Product and
accounting schemas must be bootstrapped through authorized code; arbitrary raw
DDL and a trusted OS owner creating unregistered tables are not a confinement
boundary. Observing unregistered tables at a later managed transaction fails
closed. SQLite has no general persistent DDL-trigger facility.

The two inbox tables have UPDATE/DELETE financial guards; their producer INSERTs
retain the pending-only, immutable-ID and no-replacement triggers supplied by the
queue schema. The control tables are not financial data and remain restricted to
the lease control role. Producer and control transactions do not register the
financial authorization function. Their existing narrow authorizers still apply.

### Offline upgrade from the Python-only managed format

`status()['guard_format'] == 0` identifies the initial managed format. New acquire,
renew, explicit writer assertion, and financial writes fail with
`fence_upgrade_required`; reads and release remain available. There is no silent
startup migration and no claim that the old format already blocks old binaries.

1. Stop producers and **all** writer processes, including old binaries. Verify
   no stale process can write during the offline procedure; a lease alone does
   not prove an old binary has stopped.
2. Preserve and reconcile the complete database/WAL and current generation.
3. Release the old lease or wait until it expires. `upgrade_guards()` refuses an
   active same-boot lease with `lease_busy`.
4. Invoke `WriterFence(database).upgrade_guards()`. Under one SQLite write lock it
   validates the old format, installs the complete persistent guard set, clears
   the old owner, increments generation, and records `guards_upgraded` atomically.
5. Verify `guard_format == 1`, start a new process, acquire a fresh token, and
   reconcile command IDs before resuming producers.

Calling this method on guard format 1 only verifies the existing guards; it does
not repair them. Missing or changed protection requires a separate offline
recovery investigation. There is no temporary unguarded online migration window.
A rollback to `ad3f5b8` cannot write a protected authority. Removing triggers,
disabling them through arbitrary raw SQL, or restoring a same-path complete old
backup as the trusted OS owner remains outside the fault model. These changes
provide neither cross-host consensus nor an external rollback witness.

The regression archive `legacy_ad3f5b8_uta.tar.gz` contains the original `uta/`
source and original LICENSE from commit
`ad3f5b894f96ed6857a061b71290047ae1d4d0e7`. Its checksum and source URL are retained
in `legacy_ad3f5b8_provenance.json`. Tests verify the archive checksum, extract only
regular files/directories below `uta/` plus LICENSE, and verify the original
storage source hash before launching the old process. CI needs no historical git
object and never substitutes current source for the old implementation.

```sh
python -m unittest discover -s tests -p 'test_writer_fence*.py' -v
```

The extended suite verifies old processes created before and after activation,
actual matcher settlement by the current writer, guards on newly created tables,
missing guard/metadata refusal without repair, runtime SQL expiry with complete
rollback, and the explicit old-format upgrade. Retained red evidence and these
green checks must be reported separately; the earlier authorizer-only acceptance
must not be interpreted as proof about old binaries.
