# Bind the negative verifier output path

The independent673 review (OWN36a4f1b, followed bybc24a57) demonstrated that a
runtime negative's `--output` could name a different file from its pinned report
reference and still be accepted. The original accepted red remains unchanged.
This new isolated commit requires both names to be canonical absolute paths
and exactly equal, in addition to all earlier source/input/archive/check-matrix
bindings. Relative paths and aliases containing `.`/`..` or symlink resolution
cannot substitute for the recorded output. The valid positive control stays
accepted.

This supersedes the older R5 note permitting renamed archived report copies
for execution authorization. Copies remain useful review evidence, but the
authorizing reference must identify the actual recorded canonical `--output`.
Do not rewrite an old argv to fit a relocated copy; collect a new qualified
package record when the original is unavailable.

The exact original peer script is retained byte-for-byte in
[`evidence/runs/managed-runner-output-binding-closure`](../evidence/runs/managed-runner-output-binding-closure).
Only its pure report-control AST block at original lines58–75 was executed.
Its `main`, original-vector subprocess and dummy lifecycle were **not** run.
The same positive then mismatched-output control now records `accepted=false`.
Nine package-only data tests pass on each of3.10/3.12/3.13. These are synthetic
ZIP/TAR/report fixtures, not a package build, collector/verifier invocation,
SQL, service or benchmark. Four raw-type/identity findings remain open for a
second commit; execution remains NO_GO pending independent closure and fresh
exact-source qualification.

Rollback restores the previous diagnostic candidate in a new commit, keeping
the original red and this control record. No source freeze, authority, ledger,
stability producer or observer is changed by this fix.
