# Independent producer idle-reader review: 6cc6ab0

Reviewed integration: `6cc6ab01d9645cfc2bb7b1cb5654b6cd90be10c1`.
Prototype: `f92a2d61e0f6dac3bd0e52a48428986264cd7829`.
Producer integration base: `fdb2f59b3342743e9a28eda68bb310747a1bdc63`.

This is a static cross-group review of committed code, ASTs and archived raw
evidence. No SQL, test, service, live sample, signal, original paused job,
forensic clone or original source was executed/read by this reviewer. The
review adds only this report and a static-check manifest in a separate tree.

Verdict: **the idle-reader mechanism and lifecycle are suitably narrow; one
noncanonical-path metadata-key compatibility finding remains open.** Canonical
new-job paths used by the planned release do not exhibit that key mismatch,
but the helper should not silently narrow the accepted producer path contract.
This does not establish production or long-duration acceptance.

## Connection and WAL boundary

The helper opens exactly checkpoint, router and financial-shard main files.
The authentication database is not an observer target and has no holder.
Each main must already be a direct regular file owned by the current UID with
no group/other permissions. A no-follow metadata lookup checks identity before
open; the producer also supplies its immutable original job identities. A
second metadata lookup after open/warm requires that same current main inode.
This does not constitute complete parent-path authorization or defend against
arbitrary trusted-OS file replacement; native private-path/authority controls
remain independent.

SQLite opens `mode=ro`, `uri=True`, timeout .2 seconds and
`isolation_level=None`. It enables connection-local query_only, reads existing
journal mode without assigning one, requires WAL and reads a real B-tree row.
The checkpoint warm row exists after the run's initial controller/log state
writes, router_layout exists after completed initialization, and the required
synthetic deposits/pool/loan bootstrap makes ledger_events nonempty. Missing
rows fail; no placeholder is inserted and no financial replay is bypassed.

Every warm/query cursor is exhausted with fetchall and explicitly closed in a
finally block. No BEGIN or retained cursor is introduced, and the helper
checks `connection.in_transaction` is false before retaining each connection.
This keeps SQLite's WAL participation open without retaining a read snapshot
in the tested environments. The prototype's actual independent kernel-RO
reads, reopened writers and successful truncate checkpoints support this
narrow behavior. They are not a universal guarantee under arbitrary unlink,
I/O failure, crash, storage or SQLite-version changes.

No raw database descriptor, live immutable/nolock shortcut, background thread,
writer role, token or observer write privilege is introduced. The producer
owns these SQLite connections; the external observer stays kernel read-only.
The helper closes partial construction on failure and restricts cleanup to its
creating thread. It must not be used after fork or handed to another process:
there is no owner-PID/fork-reinitialization protocol in this class. The actual
producer path launches exec-based subprocesses with ordinary close-fds
behavior and does not pass holder objects into a multiprocessing child.

## Producer lifecycle and original gates

The constructor sets the field to None before initialization and hashes the
helper in the existing source manifest. It opens no holder during bootstrap
or initialization failure. `run()` first performs its original state writes,
then opens the holders inside the original try, before server startup and
before the original active-start CLOCK_BOOTTIME capture. On resume the
persisted start remains the authority; opening a holder cannot reset it or
add time to the old attempt.

Removing only the new holder assignment makes the complete run AST identical
to the previous producer. Configuration, duration/rate/planned rounds,
clock expressions, STOP handling, fault/retry rules, financial verification,
audit/export, final status and PASS expressions are unchanged. The holders
remain across child generations, through official drain, final verification,
log export/audit and final progress. Close drains first, closes holders, then
releases run.lock even when drain raises.

Original CLI main still invokes close in finally. Direct library callers must
also close after an exception: an existing export/status error can prevent
run from reaching its final explicit close. A close failure can interrupt the
holder's reversed-close loop; the class does not implement a general
multi-error cleanup collector. Ordinary same-thread partial-open/close and
drain-error cases are covered by the archived fixtures. These limits do not
justify a claim that every failure preserves the primary error or closes all
connections under arbitrary errors. The previously documented final-status
secondary-error limitation remains fail-closed and unchanged.

## Open metadata-path compatibility finding

The producer stores `self.directory = Path(directory).absolute()`. Absolute
does not resolve lexical `..` or ancestor aliases. Its metadata keys for
financial/router/auth paths use that lexical directory, while checkpoint's
key comes from `Database.path`, whose constructor resolves the parent. The
new helper uniformly looks up
`expected_identities[str(Path(directory).absolute() / relative)]`.

For a permitted noncanonical producer root, checkpoint's original metadata key
can therefore differ from the helper key. The lookup raises KeyError after
successful initialization and before the server, failing a path that the old
producer accepted. Canonical roots used in the micro lifecycle fixtures do
not test this compatibility boundary. This is fail-closed behavior, not a
financial bypass, and does not establish an incident in the original job.

Recommended correction: define one final-component-preserving canonical key
rule shared by lookup and the original metadata, reject ambiguous/colliding
canonical metadata keys, preserve expected inode equality and direct-main
symlink rejection. Do not rewrite historical job metadata. Alternatively,
make a canonical-root requirement explicit and reject before creating any job
state, with the compatibility change reviewed. Add owned-temp noncanonical
root/metadata cases only after authorization; no original job is needed.

## Actual evidence and pending acceptance

The prototype archives ten cases on each of three runtimes. Integration
archives ten selected cases per runtime: five lifecycle cases with explicit
server/drain stubs and five real SQLite/kernel-RO cases. These sets overlap;
they are not twenty distinct full service cases, nor sixty different cases.
Integration does not rerun all prototype negative cases against its newly
added expected-identities option. It does cover an actual partial-open
metadata mismatch and native real-connection closure.

Both archives' manifest hashes, measured source-before/source-after bytes,
result counts and raw logs agree. All records report zero failure/error/skip,
three actual runtimes and two SQLite versions. Worker elapsed duration and
unittest's displayed suite duration are separate measurements. No original
service, financial state or long run was exercised by those unit fixtures.

[Static review checks](../evidence/experiments/managed-read-holder-independent-review/static-checks.json)
bind these conclusions, the exact source commits, manifests and AST comparison.
The original incomplete six-hour attempt remains NO_GO. Any forensic
component PASS is diagnostic only and cannot upgrade its strict receipt.
After resolving the scoped path finding, final combined source still needs
full local/CI/package acceptance, separately approved real service smoke and
a newly preregistered job before any six-hour claim. Idle connections do not
prove a logical stable boundary, full business/risk reexecution, capacity,
production eligibility or the cause of old uninstrumented read errors.

## Path finding closure: 49eaa02

Follow-up `49eaa02cd290868a22afb000ba4cd19b62010b12` was independently
inspected through committed blobs. The original finding and initial 6cc6ab0
evidence remain unchanged. **The metadata-path compatibility finding is now
closed; no scoped blocker remains in this idle-holder review.**

The helper applies the same `Path(key).parent.resolve() / Path(key).name`
rule to both a new lookup map and the paths it opens. It retains the final
component for the existing no-follow regular/private inode checks; it does
not resolve a final main symlink into an accepted target. A parent alias is
lookup compatibility, not complete parent-path authorization.

All canonical metadata key collisions are rejected before SQLite, even with
identical identities. Explicit metadata must be a dict of absolute text keys
and two-element integer device/inode lists; booleans, negative device, zero
inode, malformed/missing required identities and explicit None fail with
ValueError before any connection. Omission alone retains standalone-fixture
behavior. The producer still always supplies its original metadata. Neither
the source metadata, producer directory nor original job is rewritten.

The entire producer file is byte-identical to 6cc6ab0, including run/start
clock, faults, STOP handling, source qualification, financial checks, close
and final gates. Changes are confined to helper lookup/validation, owned-temp
fixtures and the appended evidence. Actual initial mixed-metadata lifecycle
cases retain four tests with eight failing subtests and three errors. The
follow-up archives ten selected cases on each runtime with zero failure/error/
skip counts and identical measured source-before/source-after hashes.

The final fixtures use real `../` and parent-symlink roots with checkpoint's
original canonical key and lexical remaining keys. They check unchanged
metadata/directory and the same run/status/close lifecycle, same/different
identity collisions, typed invalid metadata before SQLite, final-main symlink
refusal, existing cleanup cases and a real kernel-RO read. They start no
service. Manifest, source and result hashes agree with the archived report;
the independent reviewer did not execute them again.

No-fork/single-thread ownership, nonuniversal sidecar availability, cleanup
error limits and final-status secondary-error restrictions remain as described
above. Full source qualification, actual service smoke and any newly
authorized six-hour run remain independent open gates; original paused/NO_GO
and forensic-only records cannot be promoted by this closure.
