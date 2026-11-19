# Funding target adapter output correction: independent CODE review

Decision: **BLOCKED by FTA-V3-B4** for exact source
4173d8d5315b02b5427d225718310016dfd26656, parent
1b456fd1e397ad77ba4a821c47ab6e867dae8ba0. The previous three findings have
limited static closure below; a new schema-validation classification gap remains.
All 16 adapter tests and all fault conditions in this report are NOT_RUN.

Only source/Git bytes, JSON data, AST and standard-library pattern syntax checks
were used. No target/reference import, executable target compilation, adapter or
schema-validator call, test, generator, financial calculation, SQL, proc/PID,
native actor, network or CI action was performed. The independent reference
core, case generator and answer builders were not read. This is not execution,
differential, decoder-equivalence, D2 or production approval.

## Fixed inputs and boundaries

All five delta files equal the author's physical files and fixed Git objects;
the four declared content pins are exact. The wire copy is exactly
061580ce8c13120751bde4c4ce631b9dff25aa67, 31,492 bytes, SHA256
d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be.
The UTA Git tree is identical to public16f64; the pure target blob equals ed81.
No runtime, financial rule, activation capability or history changes here.

The independent data walk checked 154 definition schema nodes and ten operation
value nodes: 164 relevant output-contract roots/nodes, with references checked
against the pinned definitions. Including operation inputs and transport schemas
gives 219 nodes. Expanded output depth is at most nine, below the guard's 32.
All actual output schemas use the six supported primitive types; there is no
number-type node or nested unknown feature in the pinned output contract.

The first administrative checker incorrectly applied closed-output object
grammar to request.properties.input, intentionally a generic transport object
before per-operation validation. It stopped with AssertionError. That reader
assumption was corrected and disclosed; it was not a target retry or a newly
discovered target failure. The generic input is outside output validation.

## FTA-V3-B4: schema support is checked along a value-dependent path

Status: **OPEN / CODE blocker**. This is a finite source-path finding in
tests/funding_hold_target_adapter_v2.py:158-217. It does not claim the unchanged
target has emitted invalid financial results, or that the pinned061 wire
currently contains any unsupported schema. The corrected implementation claims
unsupported schema branches cannot be hidden; these paths do not establish it.

At line189 an unsupported schema type is grouped with a wrong value type and
raises _OutputMismatch. The oneOf handler at181 catches that exception as an
ordinary unsuccessful value alternative. Thus the unexecuted data condition
oneOf=[{type:null},{type:number}], value=null has one matching branch while
the unsupported number type is discarded as a mismatch. The intended result
is a technical unsupported-schema failure, independently of the supplied value.

Checking type names alone is insufficient. An object alternative with a nested
unknown_feature under properties.x is rejected at its top-level value-type
check when value is null, before the unsupported child is visited. An outer
oneOf can then accept its separate null branch. This hides an unsupported key
even though the immediate supported-key check exists at every visited node.

Known-key metadata shapes also need independent validation. required="x" can
be treated as an iterable of one-character property names and accepted for
{x:1}; enum="abc" can be iterated as individual strings. An empty nested oneOf
raises a value mismatch which an outer alternative can discard. A malformed
numeric-bound field in a nonmatching typed alternative is never inspected.
These are unexecuted static conditions, not actual validator return values.

Required correction: validate the complete closed schema structure before
matching any value. Traverse every properties/items/oneOf branch and referenced
definition, including branches which will not match. Check supported type names
and native keyword shapes, required/properties alignment, nonempty bounded
alternatives, and the existing numeric/string/array constraint metadata. An
unsupported schema must raise a technical AdapterContractError; only a valid
supported schema disagreeing with its value may raise _OutputMismatch. Keep
the exact pinned wire and the financial result unchanged. New inert definitions
should cover both immediate and nested unsupported schemas and malformed known
keyword shapes. They still require separate execution evidence.

## Limited static closure of the original findings

- **FTA-V2-B1:** Successful values now reach the operation value schema outside
  business classification. Actual pinned schemas reject integer action IDs,
  query_counted=0, enum/range/type errors, missing/extra serialized fields and
  fixed-flag violations. natural_slot first requires an exact six-string tuple.
  This closes the original concrete output examples in source; B4 limits the
  broader unsupported-schema claim. Typed but financially wrong values still
  need an independent reference comparison.
- **FTA-V2-B2:** policy_identity carries the actual policy DTO and wait_records
  carries the actual validator tuple to the single final encoder. That encoder
  and final schema validation execute in the try-else block outside the business
  catch. The intermediate encoder wraps failures as technical errors. Encoder
  HoldError/InputReject faults therefore cannot take the original inner
  postprocessing-to-business-response path. There is no executed fault result.
- **FTA-V2-B3:** decompose checks an exact Totals and its complete encoded wire
  shape before calling downstream decompose. Wrong intermediate types/fields
  cannot reach that call on the inspected path. A downstream HoldError after
  BaseValues and aggregate accepted the request becomes AdapterContractError
  with its cause preserved. It cannot be normalized to an ordinary REJECT.

The original nine test methods retain exact ASTs; seven new definitions give
16. Input mapping, encoding, decoded resource walker and decoder retain their
old ASTs; only _call and evaluate changed among prior definitions. The new wire
resource contract is explicit, but matching codec behavior is not proven by
sharing those declarations. No financial formula or oracle helper was added.

## Delivery and rollback

This review adds only two SAFE documents. Preserve source4173, original fc1,
review1b456, all 16 definitions and the pinned wire. Correct B4 in a new immutable
source, then obtain another independent CODE review before any execution
decision. Do not shrink the scope or change the wire to make a comparison pass.
Rollback reverts these review files only; there is no account migration, service
hook, financial schema, ledger, position or confirmed-history mutation.
Independent differential tests, installed functionality, D2, capacity, HA,
production and real funds remain unqualified.
