# Independent resource-sampler review: f5232c1

Base producer: `763202df9cb3ce089721e5281371aff3eab58089`.
Reviewed fix: `f5232c15b8f8a2a4c814943abaff4a0dadf1376a`, with incident evidence
commit `0e8e3aead03fa709fdef00f2a0d0bc927d92e8fb` preserved.

This review only reads committed source and archived evidence. It executes no
SQL, temporary SQLite case, service, test suite, live sample, process signal,
original-job read, resume or clone. It changes no producer, observer, source
freeze, job directory, clock, authority or gate.

Verdict: **the transient-resource fix is appropriately narrow, with one open
required-main symlink contract finding before final acceptance.** There is
also an inherited primary-error reporting limitation described below. Neither
finding is financial corruption evidence or permission to mutate an old job.

## Original incident and evidentiary limits

The archived final progress records `status=paused`, exit code 2,
2072.722098933 active seconds, 513/5400 DONE rounds, one controller session,
17 worker and one parent fault signal, `final_audit=null` and false six-hour,
24-hour, capacity and production flags. `logs_verified=true` is the producer's
actual log status, not a substitute for a final independent financial audit.
The six-hour, final-financial and already failed continuous-coverage gates
remain NO_GO. Historical startup/handoff observations are not current running
status. A new source needs a new job; this incomplete attempt cannot be resumed
or retimed into six-hour qualification.

The archived error identifies the financial shard WAL path. The old source's
`is_file()`/later size `stat()` sequence admits an auxiliary-file lifecycle
race, and the retained temporary SQLite last-close case demonstrates one real
compatible removal mechanism. The original run has no retained stack or
file-lifecycle trace proving that precise interleaving or a unique historical
cause. Likewise, matching generic observer error digests do not identify an
earlier uninstrumented database/phase/cause. The incident report states these
limits and retains the failed cold/strict final evidence instead of inventing
a completed result.

## Accepted scope of the fix

Only `ManagedSoak._resources()` changes among all original top-level functions
and methods. Static AST comparisons confirm every other original function,
including constructor, `run`, `status`, source qualification, verification,
fault handling, export, duration scheduling and cleanup, remains identical.
Existing workload/risk/accounting constants and budgets are not altered; two
new constant sets name the resource inventory and allowed ephemeral paths.

The sampler makes one type/size stat observation for each deduplicated path,
explicitly includes four required main database names even if directory
enumeration no longer sees them, and counts each surviving regular file.
Only `FileNotFoundError` on exactly those databases' WAL/SHM, the six legitimate
atomic-publication temporaries or the anchored event-segment temporary pattern
is ignored. Unrelated missing files, main disappearance, permission failures,
EIO and disk-usage failures propagate. `os.walk(onerror=raise)` avoids the old
recursive glob's suppression of scan errors. Symlink directories are not
recursively followed by this walk's default behavior.

This is a succession of resource observations, not an atomic filesystem image,
financial reconciliation, data-integrity proof, ownership proof or assurance
that a size limit can never be crossed between samples. The fix opens no
database or raw descriptor. Surviving auxiliary/temporary bytes still count
against unchanged byte/free-space thresholds.

## Open required-main symlink finding

`Path.stat()` follows symlinks. Consequently, a required main path replaced by
a symlink to another regular file passes `S_ISREG` and is counted. The new
required-main directory test covers a directory replacement, but the eleven
cases have no required-main symlink case. The resource result must not be
described as proof of the original regular main path or original inode.

Recommended narrow correction: use one no-follow type/size metadata lookup
(`lstat`, or the supported no-follow stat equivalent) and explicitly reject a
symlink at a required main path. Retain the exact transient ENOENT exception
set and fatal permission/EIO behavior. Add a disposable-file case covering a
required main symlink to an existing regular file and a dangling required-main
symlink. No SQL, live inode raw open/close, source repair or permission
expansion is needed. Do not turn nonregular paths into qualified resource or
authority proof. This review does not claim a real symlink replacement
occurred in the original incident.

## Callsites and inherited exception boundary

Initialization invokes no resource sample. The constructor's existing failure
path closes its resources then re-raises; the newly archived fixture verifies
the original initialization failure object survives before required database
files exist. This code path is unchanged by the patch.

Later `status()` begins with `_resources()`. A fatal main/permission/I/O error
correctly prevents publication of a normal resource report. In `run()`, an
operational error is captured before cleanup and later final `status()` is
called again. If that later resource sample also fails, its exception can
escape instead of returning the original error in final progress. Existing
event/export/cleanup failures can similarly prevent final reporting. The
unchanged run AST proves this is inherited; the fix does not introduce an
automatic successful fallback or mark an invalid run completed.

This remaining diagnostic limitation should be stated explicitly. If the next
milestone requires preservation of both primary and secondary failures,
implement a separately reviewed structured error-chain/terminal-envelope
change with bounded best-effort reporting and unconditional cleanup; preserve
both errors without inventing resource values or satisfying a PASS gate.
Do not hide required-main disappearance merely to retain the old report.

## Archived tests and pending gates

The original eight-case red log, separate enumeration red and reconstructable
intermediate patch remain. The original temporary SQLite last-close failure
is not replaced by mocked unlink behavior. The final eleven cases' three
runtime records and raw-log hashes agree: Python 3.10/3.12/3.13, two SQLite
versions, zero failure/error/skip counts. This reviewer has not rerun them.

[Independent static checks](../evidence/incidents/managed-763202d-resource-race-independent-review/static-checks.json)
bind the exact source, verify the twenty archived manifest entries and
three-runtime counters/log hashes, and compare all original function ASTs.
The next integrated source still needs its own complete local/CI/package
qualification, scoped observer availability fix and separately preregistered
new long run. No old freeze or original job may be modified to satisfy those
gates. Production and real-funds approval remain absent.

## Finding closure: 8c9238b

Follow-up `8c9238bde2328c5d4ebaab64660ee6327417f55b` was independently
inspected through committed Git blobs without moving this review worktree or
executing a test. Relative to f5232c1, the producer source differs only by
`path.stat(follow_symlinks=False)`. That is still one metadata lookup, with no
raw inode descriptor or target read. Direct and dangling required-main
symlinks are now nonregular and fail the existing required-main guard.
Missing regular main files, exact transient ENOENT exceptions, directory scan
errors, EACCES/EIO, budget thresholds and all other original functions remain
unchanged. **The required-main symlink finding above is closed.** Its original
open review and f5232c1 evidence remain historical and are not amended away.

The follow-up archives the actual test-first direct/dangling case with one
failure and one error against the previous lookup, then thirteen passing cases
on each of the three runtimes. The added nonrequired dangling WAL/temp case
checks that their targets are neither followed nor counted as regular content.
Source/test hashes, five archive hashes and reported counters match the
follow-up summary. This reviewer did not repeat those executions.

The scope remains resource measurement: a symlink in a parent directory is
outside this direct-entry closure, and no original authority/inode ownership
proof follows from a byte count. The inherited final-status secondary-error
limitation is explicitly documented and remains unchanged. The extra parent
commit's producer-owned read-connection document is a proposal only; it
introduces no runtime connection or eligibility behavior here.

There is no remaining blocker in this scoped resource-sampler review. The
original 2072.722-second/513-round paused attempt stays NO_GO. Combined-source
full validation, CI, actual packages, observer availability and any new
separately authorized six-hour attempt retain their independent gates.
