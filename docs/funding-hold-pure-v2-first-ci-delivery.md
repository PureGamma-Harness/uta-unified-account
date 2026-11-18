# Pure funding hold v2: first normal CI delivery

Candidate implementation ed81c424 has independent financial contract review
86b3c2ac and independent source review cf6f4478. Both are limited static
assessments. This commit submits a new first normal CI on the exact public head;
29 funding-hold tests and the standard workflow are pending at publication.
The old source 4e2b and its review 7519ace0 are preserved, not relabeled as v2.

The new module only computes pure USD data projections from supplied facts.
It supports registered/pending-cap/final-payable/receivable/zero state histories,
gross P/U/N/H decomposition, conditional cash-backing checks and versioned wait
projections. It does not select Isolated/Cross/PM, calculate product valuations,
accept orders or authorize any borrow/transfer/withdrawal/payment. APPLIED,
real cancellation/ACK, outbox, persistent history, global uniqueness and service
integration remain unsupported or blocked; all activation flags remain false.

Runtime inventory is explicitly 66 Python files plus the existing HTML asset.
The original 66 runtime files retain ef7508be bytes; only the new unconnected
module is added. V2/V3 source-inventory meanings are preserved, with literal V4
adding that one module. There is no financial schema or data migration.

Run the existing workflow on Python 3.10 through 3.13 and preserve the first push
and PR evidence separately. Independent reference v2, full-field adapter and
differential execution remain separate unrun gates; normal CI cannot establish
those results or any sustained capacity, HA or production qualification.

Deploy only in a fresh synthetic engineering environment. For a complete
rollback, return to the matching pre-pure deployment and its V3 inventory.
Reverting ed81 alone restores a historical unqualified candidate, not an
accepted production deployment. Keep every confirmed funding obligation,
trade, position and journal; no older snapshot may replace confirmed effects.
Production, real funds and D2 integration remain NO_GO.
