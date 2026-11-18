# Scoped publication check and detector-literal triage

The first history check covers23 commits,164 distinct path/blob versions and81
JSON versions through the immutable tip named in `first-history-check.json`.
It found no deletion or sensitive JSON string. One credential-pattern flag
caused exit1: the original CI evidence verifier contains a detector's27-byte
header marker constant. `detector-literal-triage.json` independently parses that
exact Git blob and identifies the marker without a key payload. This limited
triage accepts that one literal; it does not weaken the general pattern or
certify absence of arbitrary encoded data. The first flagged report is retained.

The original92,276-byte provider ZIP matches its SHA-256 and all three members'
CRCs. The separate zero-byte failed download remains explicitly unsuccessful.
This check is not a repository security audit, product test or production gate.
The initial attempt to read the verifier through a sparse worktree failed;
the triage records that error and uses the immutable Git blob instead.

An additional delivery reviewer confirmed the nine review cherry-picks by patch
identity, the complete QA-plan ancestry and absence of the rejected empty-index
commit. All62 runtime files equal component source6b7/runtimeff814d4. The
integrated branch additionally contains the reviewed QA controller and its17
pure cases; its CI must validate that tree separately. Local source6b7's matrix
does not become an integrated-tree or production pass through this publication.

The delivery note and this review documentation follow the checked tip. They
preserve the original PR22 error, first setup failure, native instrumentation
limits and rollback block for unknown process cleanup. See
`docs/spawn-registration-recovery-delivery.md` for deployment boundaries.
