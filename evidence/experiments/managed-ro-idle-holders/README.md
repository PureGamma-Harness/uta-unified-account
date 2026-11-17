# Actual owned-temp idle-RO-holder experiment

The reviewed 9f57c47 proposal was implemented as an isolated prototype on
`experiment/managed-ro-anchor`, from root's integrated fdb2f59. Nothing is wired
into ManagedSoak, a service, old job or original source. The helper and tests
only use freshly owned temporary databases. This is not a financial or long-run
qualification and does not attribute the original ten generic read errors.

Actual shared run was 2026-11-17T11:40:56.358525Z to 11:40:57.507665Z,
1.149152597 seconds, below the authorized 30-second wall ceiling. The runner
enforced a shared 29-second child budget and 512 MiB address-space limit per
runtime. Python 3.10.22 / 3.12.14 / 3.13.5 each actually ran 10 tests with
affinity `[2]`; all failure/error/skip/expected-failure/unexpected-success
counts are zero. Runtime suite durations were 0.323087, 0.264875 and 0.264242
seconds. Actual SQLite versions were 3.53.1 / 3.53.1 / 3.46.1.

Prototype parameters: exactly three existing private direct regular mains,
`mode=ro`, `uri=True`, `isolation_level=None`, timeout 0.2 seconds, query_only,
and an existing WAL requirement without setting journal mode. Warm reads are
one actual B-tree row from checkpoint state, router_layout and ledger_events.
Each actual cursor is exhausted and explicitly closed, then the connection is
retained idle without BEGIN or active transaction. Identity is checked before
and after original SQLite open/warm; partial construction closes all opened
connections. Cleanup is idempotent and restricted to the owning thread.
There is no background thread, writer token, raw database descriptor or live
immutable option.

Actual fixture outcomes include all three WAL/SHM pairs remaining after the
last writer closes, followed by separate kernel-RO bwrap children reading all
three DBs successfully. Those children proved the mount readonly with an
expected EROFS non-database write probe and used ordinary mode=ro SQLite, no
immutable flag. Reopened actual writers advanced rows and a second kernel-RO
reader saw the new counts. Writers performed eight small additional writes
per DB and an actual truncate checkpoint returned `(0,0,0)` with WAL size zero
while the holders remained open. There was no pinned reader snapshot in these
fixtures. No throughput, RSS, latency, capacity or six-hour claim follows.

All real warm cursors were observed closed, all retained connections were
autocommit, and query-only rejected actual DML/DDL. Missing files created
nothing. Direct/dangling main symlinks, native wrong-format or non-WAL mains,
and actual inode replacement around the original SQLite connect were rejected.
Original SQLite functions executed throughout; wrappers only observed actual
cursors/connections or performed an owned-temp inode replacement. Partial
open failure closed both real connections; a wrong-thread cleanup was rejected
and owner-thread repeated close succeeded. No production lifecycle flag or
verification result was fabricated.

Limitations remain: final-component identity checks are not a complete parent
path authorization proof, existing source/lease/private-file controls remain
necessary, and arbitrary unlink/I/O/crash can still invalidate sidecars. An
idle holder does not establish a financial snapshot or logical point. The
source-side contract needs separate lifecycle integration, original metadata
identity checks, final source qualification and an actual service smoke before
any separately authorized new six-hour attempt. No old job was changed or
restarted and no strict receipt was generated.

The exact runner, raw logs, versions/actual affinity, result counts and unchanged
prototype/test hashes are archived. It uses exclusive log creation and must not
overwrite this execution. A fresh reviewed worktree/output location is needed
for a distinct experiment.
