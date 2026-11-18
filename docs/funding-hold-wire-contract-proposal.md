# Funding hold D1: signature and wire contract proposal

This is a **schema-only proposal for independent review**, based on candidate
`4e2b41d64b867e0b3a29e3c3ca25bc64f9d0e357`. It supplies no financial algorithm,
expected financial result, test builder, executable reference or digest answer
vector. All target and reference execution remains NOT_RUN. D2 remains BLOCKED.

The companion
`evidence/designs/funding-hold-wire-contract-proposal/contract.json` records all
13 public data class field declarations and 15 public callable/property
signatures by AST inspection, their fixed output flags, the stage/reference and
payment/wait outcome vocabularies, and the six positional `natural_slot` fields.
The source pin is 23,278 bytes with SHA256
`5c41504f58ae97c4437e7887985ef71bf65ce11b34b5d1bf923b08b6c529e67f`.
No target code was imported, compiled or executed to obtain this inventory.

The duty ID fields and canonical encoding were already specified by PR61 rev2
`8008a0b24e8dc0095420b18f6b154c9db655a183`, independently reviewed at
`446af54a5da53728de006ead3afc8f752df2bd4c`. Their original bytes remain unchanged.
The wait-policy and action hash details below are observed candidate choices
offered for review. PR61 did not previously settle their exact wire encodings.

| Identity | Candidate public name | Exact payload and namespace status |
| --- | --- | --- |
| Duty | `DutyKey.duty_id` | Nine fields specified in PR61, including `schema=1`; returned `funding-duty:v1:` prefix is outside the hashed JSON. |
| Wait policy | `WaitPolicy.digest` | Seven policy fields, including `format=1`; lowercase SHA256 has **no prefix or additional domain separator**. There is no runtime `policy_digest` property. `expected_policy_digest` is the consumer argument. |
| Shared action | `ActionKey.action_id` | Seven fields: `authority_id`, `authority_generation`, `account_id`, `settlement_asset`, `allocation_id`, `action`, `terminal_goal`. Constants are `USD`, `CANCEL_QUERY`, `CONFIRMED_CLOSED`; returned `funding-action:v1:` prefix is outside hashed JSON. No schema key is added to the payload. |

The JSON lists every included field, excluded field, exact scalar type and
canonical serialization setting. Canonical hashing uses sorted keys, comma and
colon separators without whitespace, ASCII JSON with `ensure_ascii=true`, no
NaN, BOM or trailing newline, and exact integer values. An independent reference
can construct the listed payloads and compute SHA256 independently. It must not
call the production helper or treat a digest as authorization.

The source returns `natural_slot` as a Python tuple ordered by `authority_id`,
`authority_generation`, `symbol`, `period_end`, `settlement_asset`, `account_id`.
A positional JSON array is a proposed transport representation; D1 implements
no JSON DTO decoder, REST endpoint or WebSocket contract. Exact-integer codecs,
duplicate/unknown key handling and transport authentication require separate
implementation and review. The unit scale and aggregate bounds are explicit in
the JSON; an implementation must preserve arbitrary-precision integers and
must not round them through binary64.

The action ID deliberately excludes duty, claim, policy, rule scope, interval
and scale. Those changes must not grant another query budget for the same
allocation. The proposed policy is one durable canonical action record owning
the shared dispatch count and high-watermark, with each linked duty retaining
its debt and deadline. A different policy must conflict with the existing action
instead of resetting its attempts, start or deadline. A missing or unknown
prior record cannot establish permission to initialize a fresh action.

The following decisions remain OPEN and block a D2 or global safety claim:

- Approve or version the candidate's bare policy digest and explicit action
  payload; neither becomes a previously normative contract through this report.
- Define the authority that chooses the immutable first policy for a shared
  action. Possessing its digest is insufficient.
- Define authoritative allocation ownership and lineage so relabeling, splitting
  or reissuing one economic encumbrance cannot reset its budget.
- Specify pending-action history migration across a genuine financial authority
  generation change. Worker, lease and claim changes never change this field.
- Implement durable uniqueness, complete-history recovery, CAS/outbox and real
  cancellation/fill acknowledgement. The D1 tuple validator can only detect
  duplicate IDs inside the supplied tuple; it cannot establish global closure.

`PREVIEW_BACKING_ELIGIBLE` is a conditional projection, not permission to pay,
release an encumbrance or record APPLIED. WAIT/default-review outcomes never
forfeit debt or release holds. DTO flags remain `activation_permission=false`;
pending receivables gain no early spendable credit through this proposal.

Delivery changes only this document and its JSON companion. There is no runtime,
inventory, data migration or deployment step. Rollback is a revert of this
documentation-only commit. Existing source, PR61 and independent reports remain
unchanged. No SQL, process lookup, worker, clock read, CI or network action was
performed, and no production or real-funds gate is closed.
