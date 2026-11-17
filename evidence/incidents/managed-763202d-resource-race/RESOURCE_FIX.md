# Future producer resource-sampling fix

This patch changes only resource enumeration/size observation in the new
producer worktree, plus its temporary-fixture tests. It does not repair, resume
or requalify the original attempt.

Each discovered path now has one size/type stat instead of `is_file()` followed
by a second stat. Known checkpoint/router/shard/auth main files are explicitly
included even when already absent from directory discovery; absence or a
nonregular replacement is fatal. Only ENOENT for those four databases' WAL/SHM
names, the six exact `_atomic` temporary names, and the producer's event-segment
temporary-name pattern is exempt. A surviving auxiliary or temporary is still
fully counted. Permission failures and other stat I/O failures propagate.
Recursive discovery uses `os.walk(onerror=raise)` because the independently red
directory-enumeration test demonstrated that this runtime's pathlib recursive
glob silently suppressed both EACCES and EIO. Ordinary missing files and
unrecognized `.tmp`/SQLite-suffix names remain errors.

The original byte/free-space thresholds and status decision are unchanged.
Directory sizes are necessarily successive observations, not an atomic
filesystem snapshot or financial reconciliation. No SQLite connection is
opened by the sampler, and no raw database FD is used. Duration/rate/planned
rounds, fault cadence, accounting, source/qualification gates, clocks, long-run
eligibility and `run()` cleanup are unchanged.

The constructor performs `_resources()` only after successful initialization,
through later `status()` calls; the initialization exception path closes owned
resources without invoking that metric. A dedicated fixture fails `_initialize`
before any main DB exists and proves the identical original exception escapes
without a metric call. A real main-loss or directory I/O failure is deliberately
fatal, including during later reporting; it cannot be turned into a successful
progress report by dropping that file from a byte total.

Test first retained the original eight-case fixture and raw red result:
13 negative subtest failures and one native FileNotFoundError. The actual
SQLite writer connection commits a small temp database and its real last
`close()` checkpoints/removes WAL after the first successful stat; old source
then fails its second size stat. A separate directory-enumeration negative was
red for both EACCES and EIO before replacing recursive glob. The intermediate
source hash and reversible `directory-walk-change.patch` preserve that stage.
The initial fixture used a `Path.rglob` discovery hook; the final fixture hooks
the new `os.walk` boundary while retaining the same real delete-after-discovery
semantics. Neither hook manufactures an exception in the SQLite lifecycle test.

The final 11 tests pass under Python 3.10.22, 3.12.14 and 3.13.5, each command
restricted by `taskset -c 2`, with ResourceWarning promoted to error. Suite
durations are 0.043, 0.050 and 0.046 seconds, respectively; all failure/error/
skip/expected-failure/unexpected-success counts are zero. Runtime/SQLite and
affinity metadata probes are separate small processes using those same exact
executables and taskset; raw test commands and logs are recorded separately.
No service, cold clone, original-job SQL or long workload was run.

The resource-stop fix does **not** establish reliable live observer reads.
Source-side auxiliary lifetime needs a separate reviewed design and tests;
the original ten uninstrumented OperationalErrors retain unknown causes.
The original financial-final and six-hour gates remain NO_GO. This focused
micro result requires subsequent combined-source full three-runtime, CI and
package qualification before any separately authorized new long attempt.
