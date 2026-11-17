# Noncanonical holder metadata compatibility follow-up

This appends to exact integration 6cc6ab0 and addresses independent finding
`5ded077a914594d13a38107270cd2d6c9b35969c`; neither that finding nor earlier
source/red evidence is amended. All execution used owned temporary SQLite and
explicit server/drain stubs, with no listener or business service started.

Original metadata intentionally mixes checkpoint's `Database.path` canonical
parent with lexical router/shard/auth paths. `ManagedSoak.directory.absolute()`
can retain `..` or parent aliases. The four-case first run reproduced failure
against the unchanged 6cc helper: both real noncanonical lifecycle variants
failed before the start stub, and structural negative cases were not handled
with the required typed error. It retained eight failing subtests and three
errors in 0.230 seconds. Its exact initial test fixture and raw output remain.

The helper now builds a new lookup map with the same rule for metadata keys
and its own open paths: `Path(key).parent.resolve() / Path(key).name`. It never
resolves the final main component. Original metadata and `ManagedSoak.directory`
are neither normalized in place nor rewritten. Every canonical key collision
is rejected before SQLite, even for identical device/inode values. Supplied
metadata must be a dict with absolute string keys and two-element integer
device/inode lists (nonnegative device, positive inode, no bool/float/string
coercion); malformed data and missing required keys produce ValueError before
opening a connection. Explicit None is invalid; omitting the argument retains
the standalone owned-fixture behavior. Production always supplies job metadata.

Opening via the canonical parent preserves the final nofollow type/identity
guard. A real final symlink beneath a permitted parent alias is still rejected
before SQLite. The change is lookup compatibility, not a complete parent-path
authorization proof. Native private-path/authority roles remain independent.
Existing cleanup/error limitations and final-status secondary-error behavior
remain unchanged. There is no clock, budget, fault, replay or gate edit.

The lifecycle fixture now creates the original mixed metadata shape, rather
than accidentally assigning lexical keys to every database. It exercises real
`../` and parent-symlink-alias directory roots through original run/status,
checkpoint events and export/audit, preserves input metadata/lexical directory,
and proves holder close after actual progress publication. Additional cases
cover same/different-value collisions, missing/invalid metadata before SQLite,
and final symlink refusal. Old lifecycle failures/cleanup and one actual
kernel-RO child read are included in the final ten-case target.

Actual final three-runtime target ran sequentially on CPU 2 with ResourceWarning
fatal and 512 MiB AS cap. Python 3.10.22 / 3.12.14 / 3.13.5 each ran ten cases,
all zero failures/errors/skips/expected failures/unexpected successes. Actual
suite times were 0.748311 / 0.571312 / 0.564230 seconds. Shared wall duration was
2.206042169 seconds, 2026-11-17T12:02:02.791706Z to 12:02:04.997736Z. A shared
29-second child deadline enforced the authorized 30-second ceiling. Exact
argv, interpreter/SQLite versions, actual affinity, source-before/source-after
hashes and complete raw logs are retained. No service smoke, original job/
source/clone SQL, original-source mutation or long workload was performed.

Original incomplete six-hour, financial-final and coverage gates stay NO_GO.
These are compatibility/unit results, not full release, transport or financial
qualification. Final source still requires independent closure review and the
root's combined three-runtime/CI/package qualification and separately
authorized smoke/long attempts.
