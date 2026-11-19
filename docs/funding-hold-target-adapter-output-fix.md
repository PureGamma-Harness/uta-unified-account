# Target adapter: complete output and intermediate contracts

Candidate correction for independent BLOCKED review 1b456fd1 of source fc1da5a7.
The original source and its NOT_RUN evidence are preserved. The current wire
copy is the exact new resource-contract revision 061580ce, SHA256
d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be.
The older code-candidate.json belongs to fc1da5a7; use code-candidate-v3.json
for this separate correction, not the historical pins as current inputs.

Successful values now pass the pinned operation's complete output schema after
encoding, outside the business-error catch. The limited schema interpreter
requires exact native bool/int/string/object/array/null, exact closed fields,
constants, enums, references, alternatives, numeric/string/array bounds and
patterns. It rejects unsupported schema features. Alternative matching catches
only value mismatches, so an unsupported branch cannot disappear behind a
successful alternative. No financial equation or oracle helper is introduced.

Both policy_identity and wait_records now return their actual target objects
to the common encoder; no inner encoding occurs inside the business catch.
The actual validator tuple and its order remain intact. Native natural_slot
must already be a six-string exact tuple before wire-array conversion.

The composed decompose operation validates the intermediate aggregate's exact
Totals type and complete wire structure before invoking the next target.
Invalid intermediate encoding or fields are technical failures. A downstream
HoldError after BaseValues and aggregate accepted the request is also a broken
composed target contract, with the original error retained as its cause; it
cannot become an ordinary invalid-customer-input response. Other unexpected
target or constructor failures still escape as technical failures. Complete
reference comparison remains necessary for financially wrong yet well-typed
values; structural validation does not establish financial correctness.

Seven new test definitions cover malformed action IDs, integer query_counted,
inner encoding exceptions, invalid intermediate type/fields, downstream
rejection, lossy natural-slot conversion and unsupported alternative schemas.
The original nine definitions remain. All 16 tests are NOT_RUN. No target,
reference, SQL, actor, install, import, compilation or CI ran for this correction.
Only source/JSON/AST data checks have been performed; an independent new CODE
review is required before any execution decision.

The source remains a test artifact with no service hook or financial migration.
Rollback reverts only this new correction and retains the original blocked
source/review. No ledger, trade, funding obligation or account history changes.
No comparison, decoder equivalence, D2, capacity or production gate is closed.
