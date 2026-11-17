# MAIN-only verification candidate: static, tests NOT_RUN

Implementation5924336a94688fccd5bd55c29a0b428914591f52 changes exactly eight
SQL string literals in `DurableLedger.verify` and `_verify_protection`:
financial table SELECTs, integrity/FK pragmas and the protection catalogue read
explicitly use MAIN. F01's postings-definition helper already used MAIN and is
unchanged. Removing only these new MAIN qualifiers recovers the exact previous
whole storage module AST, including all math, errors, transaction logic and
other methods. No TEMP catalogue query, authorizer exception or new privilege
was added.

Twelve controls were fixed before actual execution. They include the original
MAIN hash/balance masking cases, plus bad MAIN postings, version and scales;
F01's bad MAIN catalogue must remain rejected. Healthy MAIN accepts despite
bad TEMP rows. A real raw SQLite authorizer denies every TEMP read for the good-
copy case, proving this path needs no TEMP-read permission. Real native managed
read and raw-unregistered refusal, caller-owned transaction lifetime and the
original different-MAIN-path refusal are covered. Existing F01 sixteen controls
and thirteen original StorageTests remain in the same proposed batch.

Root must approve exact candidate and driver SHA before one CPU4/Python3.12
batch of41 tests. Use fresh0700 output, fourteen-second child alarm and a strict
fifteen-second external whole limit. New MAIN/F01 fixture databases and original
raw output are retained; original F02 baseline/candidate databases and F01
counterexample are never changed. A failure or budget/short-count condition
remains recorded with no automatic retry. No additional SQL has run for this
candidate yet.

Verification's authority is MAIN. This does not redesign legacy raw caller
provenance or claim all Database subclasses/row factories are independently
trusted. Managed registry, token, role and thread checks remain separate and
unchanged. Other ledger methods remain outside this change. The independent
ordered-postings branch is not present here; its metadata/payload SQL must also
be MAIN-qualified and independently retested if combined later.

Deploy only a newly qualified artifact after independent and complete source
acceptance. There is no schema/data migration or repair; preserve refused state.
Rollback must retain all original evidence and must not relabel a false
certificate. No production, HA, capacity or real-funds approval is granted by
this static candidate or its future author component alone.
