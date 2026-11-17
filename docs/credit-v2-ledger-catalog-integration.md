# Persistent-main ledger-catalog integration: original interface red

Whole mergefbfbfeabc65a05af47ad510bd600d7f1f404b064 integrates root's
5a2961134aedaef9914d4cdd0247bb8795fb9b90, including author4c260d2 and its
independent persistent-MAIN canonical ledger-definition acceptance. It does not
import the performance R&D branch. The financial math and native closing rules
are unchanged. Storage merged without a conflict, retaining the verified
existing-only constructor branch.

The first new-fixture native test on that exact merged source failed once at
2026-11-17 15:35:22.649781–15:35:23.042360 UTC, CPU3/Python3.12 (0.393s process,
one case0.218s), before any compatibility edit. The new original
`DurableLedger.verify` correctly invokes `_verify_postings_definition`, but the
older read-method-only `_LedgerVerificationView` used by native same-connection
preflight had not exposed that new static checker. The actual AttributeError is
retained under the original `credit_financial_source_invalid` refusal, not
relabelled a business rejection or a successful installation.

Actual fresh-control rollback inspection confirms no native marker/catalog,
no queued command or debt, no writer owner, generation0 and only the original
two journals/pool receipt. The foreign-key check is clean. Original retained
databases and historical results were not reopened or rewritten. Raw and exact
code hashes are in `evidence/runs/credit-v2-ledger-catalog-integration/attempt-01`.

The required compatibility change is only a direct static alias to the actual
original `DurableLedger._verify_postings_definition` on this local read-only
verification view, so the whole original verifier still runs on the actual
caller connection. It must not add a fallback, fake verified state, role,
transaction, successful callback or unknown-build permission. The original
failure remains an integration counterexample; fresh positive and strict
negative checks must be separately recorded after the alias.

The accepted checker scope is the persistent MAIN canonical definition. The
known raw unmanaged joined TEMP-shadow boundary remains separate. This merge
does not claim complete schema closure or close that boundary. The final fixed
M3 SHA still needs full supported-Python, CI and new-package acceptance; the
default-disabled synthetic draft remains overall NO-GO.

Compatibility OWN060022cd3050e2ffc0af50aece26d2ab57e90bd4 adds exactly
the actual original static checker alias to the existing read-method-only view.
The separate tests call the original full verifier on one real read snapshot:
canonical financial state passes without DDL or role changes; removing only the
event FK while preserving all original postings and immutable guards rejects
with the exact original `LedgerError("journal postings table definition changed")`
as the source-invalid cause. No fallback or reconstructed successful callback
is used.

Those two new controls plus only the original failed new-source native target
passed once on CPU3/Python3.12 at15:38:36.252738–15:38:43.908003 UTC
(7.655s process, three tests7.493s). The fresh target actually installs the
complete capability, acquires a real token, commits its sourced four-leg loan,
reopens/verifies the ledger, replays/query-retries the original CID without a
second effect and checks public501/readinessfalse. This is new-source evidence;
no old code-bound database or previous PASS is inherited. Raw is in `attempt-02`,
while `attempt-01` remains the unchanged original integration red. Independent
review of the narrow alias and final full-matrix/package gates remain required.
