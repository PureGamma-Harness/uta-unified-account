# Independent CODE review of the private Enum observation tag

Reviewed immutable source `7030d121ba311274a3259917dffb8daa18ae75c7`, tree
`75739e98f14c1895a1431365d054a5c6069f59a0`, whose sole parent is published PR42
source `f510bf5fea852ca04c87930077861c312320141f`. The candidate worktree was
read only. This report is committed in a separate independent sparse worktree.

Decision: the minimal Enum runtime compatibility change is **CLOSED in static
scope**, with no serializer/validator/exclusion relaxation. The proposed first
pure execution remains **BLOCKED pending the two concrete closure items below**.
No execution GO or test result is granted. No target was compiled, imported or
executed; no whole artifact, test, SQLite connection, worker, thread, process
inspection, signal or network probe was run. Metadata-only JSON/hash/Git reads
verified the declared input inventory and never executed target source.

## Runtime and identity findings

The only runtime diff is `uta/writer_fence.py`: nine added and two removed lines
introduce the Enum import, private `_LeaseObservationTag.V1` declaration and its
singleton binding. All other annotation, tuple/type, `is` provenance, error,
registry, lease, SQL and financial statements remain textually unchanged.
`uta/credit_artifact.py`, the module list, live-state exclusions, artifact format,
validator and tools/run_validation.py have zero diff from the stated parent.

The original uppercase scan includes `_LEASE_OBSERVATION_TAG` and does not
exclude it as live state. The unchanged serializer rejects a plain object and
already describes Enum type/module, member name and recursively serialized value.
The new tag therefore has an existing finite supported representation rather
than a new bypass. `_loaded_modules` includes both the uppercase tag binding and
the own-module Enum class member `V1`. `_module_functions` also scans the
own-module class's actual function entries, including its Enum `__new__` code.
The complete writer source remains in the artifact source map. No arbitrary
object support, special name skip or new exclusion is introduced.

This is in-process telemetry provenance, not financial authority or a boundary
against code that can access module internals. The six selected methods retain
manual expected descriptors, original exclusions, whole-artifact creation and
validation, unsupported module/code constants, Enum value/type changes, six
unknown existing payload forms, original exception identity/args/code/cause and
typed publication filters. The source declares twenty bounded case groups;
this review reports no executed method/subcase count. Test mutations restore
the original code and constants.

All 64 declared physical inputs match their plan lengths/SHA and exact 7030 Git
blobs: 61 UTA Python files plus test, driver and unchanged validation source,
total 1326122 bytes. The current physical UTA `*.py` inventory is exactly those
61 paths. The retained-buffer loader rejects UTA imports absent from the map,
and the validation predicates are selected from retained validation bytes.
No current code in this focused path requires `_sqlite3.__file__`; the artifact
uses `sqlite3.sqlite_version` and the driver pins the interpreter binary. A
built-in SQLite module is not rejected merely for lacking an extension path.
Actual complete-artifact compatibility on that runtime remains NOT_RUN.

The first CI's specific unsupported attribute was not retained. Static source
identification of the old object tag does not fill that historical gap or prove
all 25 errors in each job had the same cause. First CI remains failed.

## Required closure before first pure GO

`COT-CODE-001` — Close the whole artifact's source-map loop. Imports execute
retained verified buffers, but the unchanged real artifact enumerates physical
`Path.rglob('*.py')` and rereads physical source. The focused full-artifact test
checks only writer_fence.py against a second physical read. It does not assert
that the complete returned source map equals all 61 retained source pins, and
the driver does not reject additional Python source paths. The current inventory
matches, but the proposed execution does not itself establish that equality for
the artifact it calculated. Add the exact expected full source map to the
existing full-artifact method's namespace and compare the complete map, or
provide equivalent source-bound caller evidence. Keep the real artifact and
validator unchanged; do not monkeypatch their fingerprint logic or reduce the
six-method scope.

`COT-CODE-002` — Bind the caller's enforcing FD-level raw envelope. The driver
reserves a shared Python-stream budget before its os.write loop, but target or
native direct FD writes bypass RawStream. Its dup2 redirects those FDs directly
to first raw files, so an ordinary parent pipe collector would see only the
launcher's separate streams. Timeout/taskset diagnostics also originate before
that redirection. The plan lists a caller requirement but contains no frozen
enforcing parent runner covering all actual stdout/stderr paths. Provide that
exact closure before execution; a post-size check alone is not enforcement.
The runtime Enum fix need not be redesigned for this item. Preserve one actual
caller argv/Git/exit/reap/monotonic record, hard 20-second host limit, CPU 1,
shared 262144-byte raw ceiling and 512-byte trailer reservation, with missing,
timeout, drift or incomplete output classified UNKNOWN and no implicit retry.

The six-method driver deliberately treats its supplied commit as an invoker
label. Root's caller must therefore independently bind actual full Git HEAD,
plan SHA and all physical/Git pins, then verify post-state. This is explicit
in the proposed plan and is not an independent election or remote attestation.

## Delivery and rollback limits

There is no schema or data migration. The source changes current code identity;
old retained artifacts cannot describe it as current. A future synthetic rollout
needs a fresh matching artifact and authority after its own gates. Do not replace
a code-bound live image or edit activation markers. Reverting only to PR42's
old object tag returns to a known incompatible candidate, not an accepted
rollback image. Preserve commands, confirmed financial effects and UNKNOWN IDs.
Neither the earlier base nor this static review grants production approval.

After these two closure items are resolved, root may authorize one exact first
focused execution. No whole CI, native recovery, financial activation, capacity
or production claim follows from that future pure result.
