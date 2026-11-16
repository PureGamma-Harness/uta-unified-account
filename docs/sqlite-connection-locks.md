# SQLite connection identity checks and startup leases

The connection preflight previously opened and closed the published database
inode outside SQLite on every transaction. On POSIX systems that close can
cancel the process's existing SQLite file locks, even though another connection
still reports `in_transaction=True`. This is an application bug across SQLite
versions, not a reason to relax database-integrity checks.

SQLite's [first-party corruption guide](https://sqlite.org/howtocorrupt.html#_posix_advisory_locks_canceled_by_a_separate_thread_doing_close_)
states that `close()` cancels all POSIX advisory locks on the same file for all
threads and descriptors in the process. It also notes that the extra defenses
introduced in 3.51.0 are not a cure-all.

## Reproduced failure and repair

A real connection held `BEGIN IMMEDIATE` and an uncommitted insert. A separate
PID attempted an exclusive POSIX lock over the database's default SHARED range
(offset `0x40000002`, length 510). Before preflight it was blocked. With the old
code, merely calling a second `Database._private_file()` in the owning process
made that independent probe succeed while the transaction remained active.

The same result was observed on Python 3.12 / SQLite 3.53.1 and system Python
3.13 / SQLite 3.46.1. After the repair both probes remain blocked. This directly
demonstrates the lock-ownership defect and its removal. It does not by itself
prove that every earlier CI timeout, schema error or short read had this cause;
complete cross-version and workload verification remains necessary.

Existing files are now validated with non-following stat calls. SQLite opens
them using an encoded URI with `mode=rw`; removal between validation and open
cannot silently create a replacement authority. Identity and private ownership
are checked again before connection configuration. Shard and existing-auth
database overrides use the same no-raw-close principle and retain their missing,
empty-file, permissions and symlink rejection policies.

For fresh creation, an unpublished private temporary inode is closed **before**
its atomic, exclusive hard-link publication at the database path. A competing
initializer is never replaced. Authentication initialization follows the same
rule. The directory is trusted local operator state; source/path replacement by
the OS owner is outside the security boundary. Parent-path and pre/post-inode
checks do not claim to defeat a hostile filesystem owner.

Read transactions now require an existing authority, including ordinary
`Database` instances. Neither a missing initial path nor removal after validation
creates a new database. The creation policy is scoped to connection construction
with a context variable, preserving no-argument subclass connection hooks and
avoiding mutation of a shared `Database` object's flags. An explicit write
initializer can still create a new authority after a failed read.

The existing exact guard inventories, SQL definitions, fencing tokens, expiry
checks and same-commit schema/guard publication are unchanged. A genuinely
unregistered table remains `fence_guard_corrupt`; nothing is repaired or ignored
to make a reader proceed.

## Independent startup scheduling defect

Worker initialization previously consumed part of its acquired lease, then
reported READY and scheduled its first renewal another TTL/3 after initialization.
A real spawned test owner with TTL 0.6 seconds was delayed only in its test
wrapper until about 0.072 seconds remained. It reported READY, expired before its
scheduled renewal, exited with `lease_expired`, and left the subsequent command
PENDING. This is a distinct proven scheduling defect, not proof that all CI
missing receipts were lease failures.

Initialization now renews the same still-valid token and checks authority before
READY. Renewal deadlines are anchored to renewal start, including the periodic
loop, so storage wait time does not postpone the next deadline. A startup that
already exhausted its lease fails explicitly without READY, a revived lease or
a new generation. No configured TTL or business-result timeout was enlarged.

## Verification, rollout and rollback

Run both suites using the actual interpreter being qualified:

```sh
python -m unittest discover -s tests -p 'test_writer_fence_snapshots.py' -v
python -m unittest discover -s tests -p 'test_worker_startup_lease.py' -v
```

The first suite checks independent-PID kernel lock ownership for main/shard/auth
preflights, forced schema/read interleavings, true corruption refusal and missing
path behavior. The second uses real spawn PIDs with a bounded test-only delay:
near-expiry initialization must renew and execute; expired initialization must
report failure and retain its expired generation. Production has no delay hook.

Stop affected old workers and readers before deployment; a mixed rollout is not
assumed safe when an old component still performs raw database descriptor closes.
Retain databases, WAL/SHM, command receipts and incident output. Run integrity,
ledger/order/fill reconciliation and original-command queries before activation.
There is no schema migration, financial formula change or reservation release
associated with this patch. Do not roll back to the vulnerable connection helper;
rollback requires another release containing the lock fix and compatible fencing.
Replay older code artifacts only in the documented isolated forensic workflow.

These targeted results do not replace the full CI matrix, capacity testing,
long-duration verification or real-funds production approval.
