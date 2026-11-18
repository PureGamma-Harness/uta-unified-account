# Funding D1: final-stage immutable lineage

Integration-owner policy clarification, pending separate independent review.
This supplements 2bb8095f and its limited review86b3c2ac. It resolves an ambiguity
raised by independent review of reference61259db9 without consulting new target
financial algorithms or using a target answer as a reference expected result.
The nullable fields in wire061580ce describe shapes, not all reachable histories.
This is this system's explicit rule, not a claim about an external exchange.

An active final stage reached directly from REGISTERED_UNASSESSED must have
exposure_ref=None and cap_ref=None, and its required FINAL_CUT final_ref.
There is no preceding U whose provenance could legitimately be attached.

An active final stage reached through EXPOSURE_RATE_PENDING must retain both
exposure_ref and cap_ref exactly equal to those in that historical U stage.
Its FINAL_CUT final_ref is additionally required. This applies to FINAL_PAYABLE,
FINAL_RECEIVABLE and FINAL_ZERO alike. Missing, partial, foreign or changed
lineage is rejected; a matching final-cut reference cannot erase the prior
exposure/cap provenance. The immutable U stage remains in history, and the
complete expected Stage plus revision is still required before advancing.

Retaining references does not retain an active U contribution. Exactly one
active stage contributes P, U, N or zero according to its kind. After U600 is
resolved to a given P246, active U is zero and active P is246; retained references
prove lineage only. Receivables never offset H, and a zero final amount has no
P/U/N contribution while retaining the same lineage. These are existing gross
accounting rules, not a new netting discount, cap calculation or APPLIED state.

The rationale is reproducible audit provenance: deleting consumed references
from the current stage makes its complete precondition and explanation weaker
and forces callers to reconstruct information that remains part of the state.
History and current references must agree. Shape/equality checks authenticate
neither referenced contents nor approvals; D2 must verify the immutable source
records and persist the transition atomically. Existing final immutability,
given-cap limits, history length and duty/rule-scope boundaries remain unchanged.

Independent acceptance must cover direct final with absent lineage; pending to
payable/receivable/zero with matching retained lineage; and rejection of missing,
changed, foreign or partial lineage. These are rule definitions, NOT_RUN. The
reference61259db9 and its generated inputs remain frozen and unqualified; any
correction needs a new versioned source and inputs, independent CODE review and
separate first evidence. No historical result may be rewritten as passing.

This commit changes documentation only, with no target, reference, DTO schema,
runtime, database migration or service activation. Rollback reverts these new
rule artifacts while preserving prior sources and every confirmed economic
record. D1 remains supplied-data-only; D2, production and real funds are NO_GO.
