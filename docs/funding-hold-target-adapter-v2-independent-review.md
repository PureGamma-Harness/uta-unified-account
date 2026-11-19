# Funding hold target adapter v2: independent CODE review

Decision: BLOCKED by FTA-V2-B1, B2 and B3. This review covers only
fc1da5a704896dae63afe309ec8807a9df0f2029, parent
479f8ff28309e4c2b479c14ff253fed096d5135e. Five new files and four declared
content pins equal the author's physical files and Git objects. The copied
independent wire is exactly a33da70026a5b0d36d5df57ae8a5736a64914ab1:
29887 bytes, SHA-256c7f1ead652921b983bab170ed3a57c984f9e3ff06495cd395af6ab617ed456c0.
The pure target bytes equal ed81c424 and public16f64. No source was modified.

Only source/Git/data reads and AST inspection ran. No target/reference import,
executable compilation, adapter call, synthetic fault, test, SQL, actor, proc/PID,
network or CI action ran. The reference algorithm, case generator, expected
answers and financial helpers were not read or used to approve this wrapper.
All nine definitions remain NOT_RUN. This report gives no execution or D2 GO.

## FTA-V2-B1: output schema is not enforced

Status: OPEN, CODE blocker. tests/funding_hold_target_adapter_v2.py112-133 accepts
any native str/int/bool/null and recursively accepts arbitrary string-key dicts,
lists and tuples. Exact DTO class, declared field names/order and two fixed flags
are checked, but the field's actual type, nested schema, enum, range or pattern
is not checked. OUTPUT_TYPES at257-258 validates only the final top-level class
for five operations. Identity and wait-record dictionaries have no operation-value
schema check at all. Complete field copying is not a complete output contract.

Two finite unexecuted fault conditions establish the gap:

- If validate_wait_records returns the exact tuple `(0,)`, lines181-185 accept
  its tuple type and emit action_ids=[0] with statusOK. Wire ActionID requires a
  string matching funding-action:v1:<64 lowercase hex>. This is a target return
  fault, not a malformed client input to normalize as REJECT.
- If preview_wait returns an exact WaitProjection with a valid record/outcome
  but query_counted=0, the top-level type passes and the integer is serialized
  unchanged. The frozen target's output DTO has no __post_init__ type validator;
  its annotation alone does not enforce bool. The wire requires native bool.
  A wrong integer/enum/nested field in other exact output DTOs has the same gap.

The fixed activation_permission and holds_unchanged fields themselves correctly
reject0/1 through isFalse/isTrue; that protection does not cover all other fields.
The existing bad-return definitions cover a wrong top-level dictionary or a
list instead of the returned tuple, not malformed contents in the right class.

Required correction: validate every operation's full output against the frozen
wire outside business classification, with native types including bool/int
separation, closed fields, refs, const/enum, patterns and bounds. Do not recompute
financial results or call the reference core. Preserve the complete real return
and report violations as technical failures. Add inert/then separately authorized
negative cases for tuple(0,), exact DTO with query_counted0 or a wrong numeric
bool, nested/extra fields, enum/range and fixed-flag mismatches.

The duty_identity branch also calls list(key.natural_slot) without checking its
raw public return. A wrong six-character string could become six strings and
fit the serialized array schema. Validate the expected native tuple and six
string entries before conversion; do not erase an unexpected return type by
coercion. Tuple-to-wire-array conversion should preserve validated data only.

## FTA-V2-B2: two encoders still run inside the business catch

Status: OPEN, CODE blocker. _call invokes _encode for policy_identity at151 and
wait_records at184. evaluate invokes all of _call inside its InputReject /
HoldError classification block at242-254. Therefore an encoder fault with an
exact known exception type at either inner call can become REJECT/UNSUPPORTED.
The comment at259 that encoding is outside the business catch is true only of
the final encoding pass, not those earlier passes.

The finite negative definition is to inject an exact HoldError or InputReject
from the adapter encoder in one of these operations and require technical escape.
No injection was run here. This identifies a source-level exception boundary;
it does not claim the current unchanged native DTO fields actually raise such
an error during a valid request. Unexpected TypeError/ValueError and unknown
HoldError subclasses already escape correctly.

Required correction: return the raw validated policy DTO and actual validator
tuple in _call's result; perform serialization once outside business catches.
Alternatively isolate only the explicitly known input/target-call failures.
Do not let the generic exception type of an adapter postprocessing failure make
it an expected matching business result. Keep all public returned IDs and order.

## FTA-V2-B3: malformed intermediate return becomes a business rejection

Status: OPEN, CODE blocker. In decompose, lines166-169 pass aggregate's result
directly into target.decompose without validating it. The target's public input
guard checks exact Totals and raises exact HoldError for a wrong type. Thus a
bad aggregate return `{}` follows the static path: wrong intermediate result,
then downstream exact-type HoldError, then evaluate's REJECT response. The
final OUTPUT_TYPES guard and a later OK-value validator are never reached.

This is an unexecuted source-path condition, not a target test result or claim
that the current aggregate implementation actually returns a dictionary. It is
required wrapper fault isolation: a target output failure must remain technical
when composed with a second public target operation.

Required correction: check the intermediate exact Totals and complete wire
structure immediately after aggregate and before downstream decompose. Such
validation must escape the business catch through a technical contract error.
Do not validate it by feeding it to a target financial helper that can turn the
fault back into a known business exception. Add the decompose-specific wrong
intermediate-type/field definitions; the existing aggregate-operation test does
not cover this composed path.

## Correct source boundaries and deferred evidence

All13 DTO field lists match actual target dataclass declaration order, and their
field sets match the independent wire. JSON Schema required-array order itself
is not an ordering constraint; it was checked as a set separately. All10
operation input field sets match. init=False activation/holds flags are validated
as exact bools before removal; nested DTOs are rebuilt, history/duty collections
become tuples explicitly, and the request is not mutated by these mapping paths.
The target supplies monetary, stage, backing, wait and identity results. Action
payload assembly uses the wire's explicitly permitted field copy and constants;
no financial equation or reference import exists in the adapter AST.

wait_records calls the real public validator and preserves its actual result
order rather than sorting, deduplicating or substituting a count. Its separate
record_count is input metadata. This correct preservation needs B1's content
validation, not replacement of IDs with adapter-computed answers.

Malformed transport/envelopes reject outside business classification with no
fabricated case ID. Raw bytes have the2MiB UTF8 bound; BOM, inferred UTF16,
duplicate keys, NaN/Infinity and malformed JSON reject. Finite floats remain
transport values and reach exact target input validation as negative inputs.
The direct decoded API rejects non-native/cyclic trees. Schema2 excludesTrue;
valid original case_id is echoed. Old expected_active_ref is explicitly
UNSUPPORTED rather than inferred into a Stage. Known exact InputReject and
HoldError/HoldUnsupported are the only business types; subclasses and unrelated
exceptions escape. The B2/B3 findings concern provenance of such exceptions,
not failure of those exact-type comparisons.

Supplemental decoder depth32,250000 nodes and128 integer digits are expressly
PENDING agreement with the independent reference decoder. A129-digit integer
can therefore be a transport resource rejection even inside a well-formed
business envelope; this must not be counted as a proven matching business
negative. No full codec equivalence is established or claimed here. A future
bounded producer must distinguish valid domain, business negative, malformed
transport and transport resource rejection, with an explicit shared contract.

The nine tests are definitions only. Full-field differential, unchanged-input
observations across all operations, matching decoders and real target/reference
results remain NOT_IMPLEMENTED/NOT_RUN. A new immutable delta must close these
three CODE findings before another independent review and any first execution
plan. Keep fc1da5a7, the wire and historical evidence unchanged. Rollback removes
this unconnected test adapter only; no service hook, account migration, ledger
or financial authority changes belong to this review. D2 and real funds remain
NO_GO.
