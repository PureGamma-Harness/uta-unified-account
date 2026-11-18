# M0 resource sampling: enumerated regular-file provenance

**Code/file-metadata candidate only; independent review pending; overall NO_GO.**
Base `1d727b9d8e121611d0227dbee162192c13a76769`; frozen new code
`be7755008782db045a03ce113aa58e6d1e84ee43`.

## Retained first results and the contract

Actual M04 run44199787770 first evidence locates a missing router SHM rule;
that result remains unchanged. Independent review
`93060e8e4d2272ada812dfcc2aaba555879dedc7` preserves its once-only27-case
batch on source1d727:25 PASS/2 RED, exit1,271191472ns. The two RED fixtures
created an exact-named `router.sqlite3-shm` directory or symlink, then removed
it after enumeration and before lstat. The old exception handler accepted a
rescan by filename/current main/parents without knowing its enumerated type.
Those synthetic types are not evidence of actual M04's entry type or cause.

This system's rule is now: disappearance can enter the existing bounded retry
only when the same enumerated entry was positively observed as a **regular
file without following symlinks**, its failing lstat names that exact path,
and its explicit role/path and current parent/main checks all still pass.
Unknown, directory, symlink and other nonregular types cannot borrow the
auxiliary filename exemption. Current known auxiliary entries must also be
regular; a directory bearing that name is rejected.

## Minimal source change

`_resource_entries` uses streamed `os.scandir` entries instead of discarded
`os.walk` names. Before the existing `Path.lstat`, it obtains
`DirEntry.is_file(follow_symlinks=False)`. Only the literal API result `True`
allows that same path's ENTRY_LSTAT/ENOENT exception to carry internal
enumerated-regular provenance. `False`, missing/unknown evidence and errors
do not. `_known_missing_sqlite_aux` defaults to false without that exact-path
provenance, including direct calls. The same gate covers router, shard and
runtime-probe sidecars; none has a filename-only bypass.

When filesystem d_type is unknown, DirEntry may need a nofollow metadata
lookup. If it cannot establish a regular file before disappearance, the
result is false or a missing-entry error and the policy rejects. Permission
and EIO are propagated as the same errors, with existing D1 classification;
they are never converted into a benign false or a retry grant.

Every queued directory is freshly lstat-checked as a nofollow directory before
descent. Each entry is yielded/accounted once before any descent is queued;
flat listings are not materialized or prefetched past the entry-limit failure.
The entry limit, byte compartments, stable-path/type tracking and per-file
maximum observed size survive retries. Existing walk-mocking tests are adapted
to scandir hooks without changing their rejection/budget assertions.

Only resource helper code and its test hooks change. Business source909,
`uta/`, workflows, approval/source/namespace pins, crypto/escrow, and all budget
constants remain byte-identical to the base. No cold-import change is mixed in.

## One authorized new-source batch

Source was committed before execution. Root's final affinity was **CPU1**, not
the superseded CPU4 proposal. The only new batch ran:

```sh
taskset -c 1 timeout --signal=KILL 10s \
  python -B tests/test_independent_m0_entry_types.py -v
```

First and only result:2026-11-18T00:05:17Z, **14 unittest methods PASS**,0 errors,
0 failures, exit0,0.049s unittest time. Original stdout/stderr, exit, source
commit, input SHA256 and start time total2730B under
`evidence/independent-m0-entry-type-provenance/pure-once01/`. Per-output file
size was limited to40KiB; the external watchdog was10s. Input hashes were
rechecked unchanged after execution. No rerun-to-green occurred.

The new batch uses tiny own temporary files and fake metadata. It covers:

- Router/shard B/P×WAL/SHM×explicit root/case roles and runtime-probe positives.
- Real directory/symlink removal before lstat, and present nonregular rejection.
- False/unknown/nonboolean hints, missing unknown-type fallback, hint Permission/EIO,
  bare handler rejection and wrong/public paths.
- Directory-enumeration failures, streamed entry-cap termination and a local
  actual DirEntry retaining its previously established nofollow regular type.
- Thirteen selected existing strict contracts on fresh fixtures: main/parent
  failures, symlinks, three-attempt churn,50ms admission/completion bounds,
  stable path/type retention, growth cap and prior size lower bounds.

The old independent27-case batch and author's186-test suite were **not rerun**.
This batch's14 methods include subcases/selected contracts; its count is not
interchangeable with those earlier case counts. Standalone audit hooks reject
SQL connection, process creation/signals, socket operations and native flock.
The metadata imports add no `uta` or SQLite module, and the import assertion is
relative to preexisting modules so normal full-suite discovery is supported.

## Evidence limits and remaining gates

The positive local DirEntry check supports this host's actual API behavior;
unknown-d_type failure is conservatively modeled with fake hints, not a claim
that the host filesystem was forced to report DT_UNKNOWN. No CPython C-source
or all-platform/version qualification is asserted. No SQLite connection,
financial workload, owner, encryption, network, CI, M05 registration/ref/push,
long-test process or private key/quarantine was touched.

Retry remains at most3 scans on the same original50ms clock. Admission at50ms
rejects; successful completion at50ms retains the original inclusive bound;
later completion rejects. These checks do not preempt an individual kernel
metadata call. Current path/type metadata is not an atomic snapshot. Same-type
parent/main dev/ino replacement, ABA and inode reuse are still unimplemented
identity boundaries; this correction does not upgrade them to guarantees or
establish actual SQLite lifecycle, performance, sustained capacity or HA.

## Deployment, review and rollback

This is an isolated local candidate, with no executable approval or refreshed
spent04 authorization. Root must merge the separate cold-import work and
review immutable final source/config pins before even proposing another actual
run. Any native validation or M05 requires separate explicit GO; these pure
passes supply no such permission. Artifact-group independent review is pending.

Rollback means reverting code commitbe775 while retaining all first raw
evidence. That restores the known type-provenance gap and must remain NO_GO;
it does not reactivate M04 or clear its failure. There is no customer-data,
schema, ledger or financial rollback because none was changed.
