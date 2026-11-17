# Future source-side read contract (proposal only)

This document proposes a small producer-owned connection-lifetime change. It
does not implement it, run a new probe, change the original attempt or claim
that any historical OperationalError has a proven cause. Original six-hour,
financial-final and coverage gates remain NO_GO. The resource-sampling patch
only fixes a separate early-stop path; it cannot establish reliable live RO
observation.

In source 763202d, `Database._role_transaction_body()` closes every SQLite
connection on exit. The benchmark checkpoint `_state()`/event/export reads and
writes therefore leave no persistent checkpoint connection. Coordinator/router
and shard worker generations have their own connection lifecycles. SQLite may
remove WAL/SHM when the last connection closes. A kernel-RO observer correctly
cannot create missing auxiliary files; its check-before-connect can still race
source-side disappearance. The ten historical OperationalErrors have only a
type/message digest in the original samples. A generic digest or a separate
synthetic CANTOPEN reproduction does not identify their database, phase,
native code or unique cause.

The minimal candidate is three **producer-owned**, existing-file URI
`mode=ro` SQLite connections for checkpoint, router and shard. Their lifetime
is the original `ManagedSoak` driver lifetime, covering planned worker and
coordinator restarts. There is no auth database holder because the observer
does not read that database. This is a source-side contract; the observer keeps
its kernel-RO mount, query-only policy, no source writes and fail-closed errors.
It does not retain a production writer token or share accounting/risk functions
with the observer.

Candidate placement is `ManagedSoak.run()`, after successful initialization,
original run.lock/source/validation/file-identity checks and initial controller
state writes, but before `_start_server()` and before the existing active-start
clock. Opening a missing or replaced main must fail; never create it or repair
a schema. Use the existing original path identity, URI encoding and private-file
checks before and after SQLite connect. Do not use raw database FDs. Set
`isolation_level=None`, enable `PRAGMA query_only`, and read—not set—journal
mode, requiring the existing WAL format. The legitimate producer's filesystem
can create SQLite auxiliaries as part of opening a RO connection; that is not
permission for the observer to write them. Actual behavior must be tested for
each shipped SQLite runtime, especially when auxiliaries are initially absent.

Warm each connection with a real, bounded B-tree read: checkpoint `state`,
router `router_layout`, and shard `ledger_events` already exist in the fixed
initialized workload. `SELECT 1` alone is insufficient. Exhaust and explicitly
close each cursor, then retain only the connection with no BEGIN, no live
statement/cursor and `in_transaction == False`. That flag alone does not prove
that a cursor has released its implicit SQLite read snapshot. No periodic
long read transaction or background sampling thread is proposed.

Keep holders through official service drain, original completed/paused event,
log export and audit, final verification, and final progress publication.
Close them idempotently in driver cleanup before releasing run.lock. If opening
holder two or three fails, close already opened holders and preserve the
original failure before starting the workload. A constructor failing before
schema creation must never try to open these connections or replace its error
with a metric/holder error. Avoid changes to global Database semantics.

SIGTERM still requests the original official drain; it does not reset clocks,
restore an old owner or skip final logs. SIGKILL/crash/host loss closes OS
connections and can leave WAL requiring legitimate recovery. A future resume
must independently revalidate authority/source identities before reopening
holders; it still cannot claim one continuous controller session. A new live
observer cannot invent a baseline after exit. Once the original driver exits,
the supported completed/stopped final path remains distinct from live reads.
A paused or failed job requires an explicitly separate diagnostic path and
cannot receive a long-run receipt.

Holding idle connections is a candidate for ordinary auxiliary lifetime, not
a guarantee against external unlink, inode replacement, permission/I/O failure,
crash or every SQLite error. Do not re-create a missing auxiliary from the
observer or downgrade to live immutable reads. All logical-point brackets,
actual driver-birth checks, unknown classification and same-final-watermark
golden/FK/reopen requirements remain necessary. There is no claimed throughput,
latency or performance benefit.

Before implementation review, prepare an owned-temp-DB test matrix only:

1. Compare genuine last-writer close with and without each warmed holder;
   observe WAL/SHM lifetime and an actual separate kernel-RO read. Include
   initially absent auxiliaries and real warm B-tree reads versus SELECT 1.
2. Prove no transaction/cursor remains pinned: another legitimate connection
   writes a small fixed number of rows and performs an actual truncate
   checkpoint successfully while the holder stays open. Retained connection
   lifetime must not create unbounded WAL growth.
3. Close/reopen only the owned temporary writer/worker generation while the
   driver holder remains; verify identity/sidecar continuity and actual reads.
   Final holder close and a tiny child exit/crash fixture must produce the
   expected closed-state behavior without manufacturing completion.
4. Reject missing/replaced/symlink/wrong-format main files and a second
   controller; preserve partial-startup errors and repeated-close safety.
   Exercise query-only denial and the same-thread cleanup contract.

The initial micro budget should be at most 10 small cases per runtime,
sequential on one explicit CPU, shared wall ceiling 30 seconds, bounded temp
rows/pages/files, and no service/load/long job. Record actual SQLite versions,
file identities and lifecycle outcomes. Those microtests have **not** been
executed by this proposal. A later service smoke or full long attempt requires
its own review and authorization after the final combined source passes full
three-runtime/CI/package qualification.

For the original paused incident, frozen observer `sample()` enables cold
access only for completed progress, so it fails the live-sidecar precondition
before an eligibility result. `producer_audit()` samples before checking its
strict final gate. Producer `audit_job()` separately requires completed,
stopped progress and verifies all `configuration.rounds`. Thus making paused
source readable alone cannot turn the existing CLI into a successful partial
cold audit, and relabeling cloned progress completed is forbidden.

A root-approved future incident diagnostic may first establish stopped
original PID births, baseline/source/start/deadline and actual filesystem
sidecar state, then use a private 0700 complete SQLite backup under the already
approved private-authority policy. Full clones include historical writer nonce
columns: never call them secret-free or publish them. Preserve complete schema,
control records and exact validation sidecars; public output remains a narrow
redacted allowlist. All source mounts remain RO. Both auxiliaries absent on a
proven stopped source and a complete WAL/SHM pair need separately correct read
modes; a partial pair must fail closed rather than discard WAL or repair the
original. No original DB has been opened for this proposal.

Running the unmodified original producer audit on a paused clone must retain
its refusal. If partial 513-round producer verification is needed, design a
separate explicit diagnostic operation using the original complete verification
logic at actual completed rounds and original planned bootstrap debt, plus log
verification, independent golden/FK/reopen and one shared watermark. Its output
must retain paused/error/incomplete-duration facts and be ineligible for the
21600-second/5400-round receipt. This requires root review before any original
incident SQL/clone work and is not part of the resource fix.
