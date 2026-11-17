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
