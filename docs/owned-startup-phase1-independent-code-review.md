# Owned startup phase1: independent static CODE review

The independent review of `6303ed46d946138c08551e30387abd3de18ab146`, tree
`7c58612afc97d1814aa00fa50df511e087c170f4`, is **CODE_ONLY closed**. It adds
observations and does not repair admission policy. This review imported or
executed no target, fixture, guard or tests and performed no SQL, target
worker/process launch, network, signal or native probe. Ordinary Git/source
metadata commands were used. This record grants no execution permission.

The exact three source lengths and SHA256 values are in
`evidence/reviews/owned-startup-phase1-independent-code/review.json`.
Comparison used `09627fdedabd2aff0b8635cf0f6b68c95e5b6409`, whose runtime
comes from the original published source `9b4fcf5df3615c8bcddc8dc37cb35f9a24d21439`.

## Findings retained and closed

At `73dd5e3`, the expired branch created its original error before constructing
the optional observation outside protection. Metadata construction could then
replace the primary. `24a8cf7` protects the entire optional construction and
annotation, then raises the same error. The original clock, token identity and
strict expiry decision remain outside this protection.

At `24a8cf7`, `assert_writer` also needed caller-level protection around its
optional annotations while an original error was propagating. `c315241`
protects only that metadata block and ends with the original bare raise.

At `c315241`, the optional diagnostic import was outside its metadata Exception
boundary. `6303ed4` moves it inside. The original mandatory WriterFence import
is unchanged. Successful-path KeyboardInterrupt/SystemExit cancellation still
propagates; optional failures during an existing primary do not replace it.
All prior findings and fixes remain in history and were not rewritten.

## Original authority and transaction decisions

Static AST comparisons establish that the original `_clock`, `_observed` and
`_ttl` bodies are unchanged. Removing only the new telemetry and optional
argument makes `_load` match its original AST. Replacing only the diagnostic
expired body with its original raise makes `_assert_token` match the original.

The original SQL execute/executemany argument AST multisets match. That alone
does not prove dynamic order or count. Source path review separately confirms
one original load per original path, reuse of the original post-UPDATE row for
the existing event, no added SQL or retry, and the original transaction context
and final fenced COMMIT. The original full ledger and credit verifiers remain.
The lifecycle methods listed in the JSON record match their original AST.

A private known-renew receipt is exposed only after the original transaction
context reports success. Startup copies it only after that exact renew call
returns and the fence's private token reference is the startup token. Unknown
COMMIT replies and a wrapper error after a real COMMIT do not establish a
known startup return. The current attempt and prior known receipt are separate;
neither repairs keeper poison or supplies authority.

## Diagnostic and timing limits

Runtime and collector field allowlists match. They permit bounded ordinary
integers, booleans and fixed clock/phase/state enums. There is no raw nonce,
authority or boot value, arbitrary message/repr or private-path projection.
Copied primitive maps are immutable and carry a private origin tag. The
collector performs the original addError bookkeeping and traceback once,
before optional collection. Existing exception args, code and chaining remain.

The intervals describe existing load/fetch/validation work, not the instant
SQLite establishes its snapshot. `snapshot_time_known` can only be false.
Fence-clock values and monotonic intervals have separate labels; they cannot
be subtracted as one clock domain. Missing optional fields remain missing.

Every read transaction, including unmanaged and unbound reads, gains timing
and metadata overhead. This review does not claim timing/performance
equivalence, a hard duration bound, physical quota, or actual SQLite/WAL,
keeper, contention, OS-pause or READY acceptance evidence. The collector's
compact-record bounds do not describe the total indented worker-file size.

## Remaining gates

Phase2 remains **NO_GO**. A fresh same-token head cannot authorize an old
financial snapshot. Complete actor exclusion or a sufficient composite
watermark is still unproven; owner-thread financial writes, post-ledger policy
writes, every allowed role and all verifier/final-COMMIT dependencies need a
complete proof. The original CI errors remain independent and UNDETERMINED.
The conditional baseline RED do not identify their histories.

The later `72dcebf` fixture/driver was received after this CODE review and is
not covered here. Its proposed 12 methods/48 fake traces require their own
static review and root's exact-source budget. No pure, native, CI, production
or phase2 permission follows from this record. Original CI, PURE, M05 and
finding evidence remains unchanged. Rollback of this independent record
removes only these two review files; it changes no runtime or original data.
