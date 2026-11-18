# Built-in SQLite binary metadata compatibility proposal

Candidate source `ee225ae59474daa094b210e97be99d6a9325acce` changes only
`binary_info()` and its69-source manifest pin. It has not been executed.
The original preflight failure at2d17fc8 and its partial runroot remain intact:
`_sqlite3` lacked `__file__`, no preflight.json existed, and actual affinity,
birth, binary and resource payloads were not persisted. The first pure20 stays
RED; isolated pure1 stays separately PASS. Both original CI causes remain open.

The candidate accepts a built-in `_sqlite3` only with an actual ModuleSpec named
`_sqlite3`, origin `built-in`, exact BuiltinImporter identity and membership in
sys.builtin_module_names; location/file contradictions failclosed. Its descriptor
has null extension path and SHA. A dynamic extension requires an absolute origin,
exact ExtensionFileLoader and one regular resolved image shared by origin,
module file and loader path. Unknown origins failclosed.

The metadata also hashes the actual regular Python executable and every named
libpython/libsqlite3 image in its own maps. Unreadable or nonregular named images
failclosed. A built-in module can reside in the executable or libpython; an
extension file is never invented. Empty loaded-library maps record absence of
an observation. This binds declared file bytes and descriptors across preflight
and run; it does not attest the whole system, every dependency or mapped memory.
The existing run check compares the complete binary dictionary for equality,
including descriptor and loaded images.

All other68 source inputs retain their exact59efb56 bytes. The entire common
prefix before binary_info, containing all guards/classes/imports/constants, is
byte-identical (SHA34bae5158be189f21f8806ce5ce597029d2301420a4ba55d9c71c1c64f660f9d).
Identical function-source bytes establish identical parsed guard/case AST nodes;
no Python parser, target import, probe or test was executed for this proof.
Parent/case timing, process ownership, protected10 PIDs, TTL2/lease1/pub8/act8,
quote SID/timestamps and all three negative controls remain unchanged.

[binary-compatibility-source-plan.json](../evidence/reviews/process-readiness-engineering/binary-compatibility-source-plan.json)
pins the candidate and proposes a fresh root for a separately authorized single
metadata attempt. CPU count1 with actual ID recorded,10s Python-line budget,
sourcecopy8MiB, disk128MiB/memory384MiB/PID12 headroom stay unchanged. Source and
manifest Git/physical binding, clean worktree and fresh-root ENOENT checks must
precede that invocation. Preserve complete first raw and partial data on failure;
no retry follows automatically. A valid metadata result never grants native GO.
