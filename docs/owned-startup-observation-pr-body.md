Owned-startup lease failures lose the used-row/renewal facts in ordinary
tracebacks. Bounded observations now preserve those facts and the original
exception. The validation worker gains two diagnostic fields, and its strict
qualification consumer now accepts exact legacy7 or reviewed new9 records;
new records must contain an empty native list and literalFalse truncation.
Unknown, half, nonempty, truncated or aliased extensions reject. This is a
default-on diagnostic change with strict report compatibility; it does not
repair read admission or authorize READY.

Summary reserved fields are checked independently: W7/S7 remains supported,
W7/S9 is accepted only with a complete native-empty/false summary pair, and
W9 still requires a complete matching S9. Other existing summary metadata is
unchanged. Earlier81a1af9 lacked that W7/S9 check; it remains NOT_RUN/zero attempts
with its independent static finding preserved.

The branch preserves PR38@17e0838, including unrelated D2 default OFF and both
first CI failures, then merges authorb59106c and independenta202499 histories.
The observation files `uta/writer_fence.py`, `uta/startup.py` and
`tools/run_validation.py` exactly match reviewed6303 bytes. The additional
`tools/run_managed_variants.py` control-layer adapter keeps all original
qualification counts/flags/source/runtime/raw-log/CI checks and per-key
worker/summary equality. It preserves complete original reports and cannot
borrow old proof for new source. No SQL, schema/data
migration, customer API/error contract, lease duration or keeper deadline is
changed. Private v1 diagnostic fields are a paired, strictly validated report
extension. Its frozen8518a0b actual-QA-prefix fake fixture completed its unique
authorized first6methods/32cases PASS,0FAIL/ERROR; full raw/host evidence is
retained. Independent CODE review c741f0f and first-RAW review d64db05 both
closed their limited scopes. The RAW review binds all eight originals, actual
host exit0/reap, seven input pins and all32 cases; it does not execute package gates
or certify an actual source's full qualification.

Evidence remains source-specific: baseline8methods/30traces includes3
conditional RED; first88da96f12methods was11OK/1FAIL/0ERROR with45 entered;
correctedbf48ae2 isolated m08 was1method/4selectors PASS. The last result does
not turn the old all12 run green. Independent CODE/raw closures are included.
This merged source has not run whole CI, packaging, native SQLite/workers or
performance tests. Assembly added only the separately authorized frozen pure
fixture run; no whole suite/build/services were executed. The focused fixture excludes package,
installed, omission, process/resource and real proof-reader behavior.

All reads gain monotonic/metadata work, guarded assertions gain a registry-lock
lookup and telemetry affects timing/allocation. No performance equivalence or
five-second recovery claim is made. The reported read/fetch windows do not date
SQLite snapshot establishment; clock domains are separate and missing fields
remain unknown. Last-known COMMIT facts never supply financial authority.

Deployment remains fresh-synthetic-only after separately authorized gates.
Existing code-bound authorities cannot be hot-swapped or have markers rewritten.
Rollback retains authorities, commands, receipts and raw history and requires
compatible code/layout binding; it never erases confirmed effects or retries
UNKNOWN work under a new ID. Full contract, compatibility and rollback details:
`docs/owned-startup-observation-delivery.md`.

Phase2 remains NO_GO; original PR38 error causes remain UNDETERMINED. Production,
real funds, native recovery, CI acceptance, HA and10k/s approvals remain false.
