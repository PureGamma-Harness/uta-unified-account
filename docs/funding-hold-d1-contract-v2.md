# Funding hold D1 contract revision 2

Status: integration-owner policy decision, pending independent financial and
verification review. This specifies the next pure implementation and reference
comparison; it does not activate settlement, cancellation or any financial API.
The original PR61 specification and the observed 4e2b implementation, 895bcf
wire proposal and independent findings remain immutable historical evidence.

## Identifiers and values

Retain the exact typed DTO fields, integer bounds, units, fixed vocabularies and
canonical JSON rules inventoried in the 895bcf proposal, except the stage-CAS
argument below. These are a new explicit D1 contract decision, not a claim that
PR61 previously fixed every encoding. There is no JSON transport implementation.
Reject bool as int, inferred aliases, missing or additional payload keys, and
lossy binary64 conversions in any future decoder.

Adopt the existing nine-field duty identity, seven-field wait-policy payload
and seven-field action payload exactly as enumerated by the proposal. Duty and
action prefixes remain outside their hashed canonical JSON. The policy's
`.digest` remains a bare lowercase SHA256 over its seven-field format=1 object.
Consumers must accept it only as a typed WaitPolicy content identity; it grants
no approval, authorization or fresh budget. A future domain-separated encoding
requires a new explicit version and migration, rather than changing this value
silently. An independent reference constructs these payloads itself and never
calls production digest helpers.

The action's allocation_id means the immutable root encumbrance lineage ID.
Account, authority, stable financial generation and USD settlement remain in
its identity. Scale is not added to the identity: a mismatched approved scale
must be rejected, and must never manufacture another action or query budget.

## Complete stage precondition

Replace the pure advance_stage keyword expected_active_ref with
expected_active_stage. Its value must be an exact Stage, validated against the
same duty and rule scope, and equal the complete current Stage, including kind,
amount, exposure_ref, cap_ref and final_ref. Retain expected_revision and require
both equalities before advancing. A malformed expected object is rejected; a
well-formed unequal expected stage is a CAS conflict and returns no replacement
state. An old single-ref keyword is unsupported, with no inferred conversion.

This checks the supplied pure state only. It authenticates neither referenced
content nor database history. D2 must load the authoritative state, verify both
content references and their provenance, and atomically compare and persist
the complete state/revision. A reference digest alone cannot stand in for the
exposure/cap pair. No final state may be amended or changed to APPLIED here.

## Wait revision and boundaries

The wait revision counts changes to the record, rather than observations or
commands. Compute proposed high-watermark, attempts, last-dispatch and sticky
default-review first. If all fields other than revision equal the prior record,
return that original record with the same revision and query_counted=false.
Otherwise increment revision once and reject overflow before returning any new
record. Apply this rule equally to normal WAIT and DEFAULT_REVIEW. A read-only
same-time observation at the maximum revision succeeds unchanged; any changed
record at that revision is rejected. Original input objects remain unchanged.

now below the persisted high-watermark is rejected. At now equal to the first
deadline no query is counted, and default-review becomes sticky. Dispatch at
the exact minimum interval is eligible only while strictly before the deadline
and below the attempt cap. Reaching the cap counts the last permitted attempt
and enters default-review. Repeated default observations, restarts and unknown
dispatch results never refund attempts, extend deadlines or release debt/holds.
A pure query_counted projection is not evidence of actual dispatch or a durable
outbox record. Physical dispatch and confirmed cancellation remain D2 gates.

## Shared action authority and recovery

The policy for a newly created action must come from the approved immutable risk
configuration effective for that account and product. D2 must record its
configuration version, approval identities and effective time in the same
transaction as the unique first action. Arbitrary caller policy or possession
of its digest is insufficient. A different policy for an existing action is a
conflict; preserve the original start, deadline, attempts, high-watermark and
restrictions. There is no hot policy replacement in this revision.

The authoritative reservation service assigns the root lineage when it first
durably reserves an economic encumbrance. Amendments, split children, replacement
allocations and relabeling of that encumbrance inherit the root action budget.
Each physical child query consumes one shared attempt. A root is confirmed
closed only after all linked children and in-flight settlement obligations are
reconciled; a parent cancellation request alone cannot close it. New independent
business reservations require their own confirmed origin, not a renamed ID.
These ownership facts are external D2 evidence, not facts a D1 string validates.

One durable canonical action owns the shared count. Each duty keeps its original
debt and deadline; attaching another duty cannot extend either deadline or reset
the action. Worker, lease and claim changes never change financial generation.
A genuine authority migration must import pending root mappings and the full
canonical history before enabling writes. Missing, conflicting or unavailable
history leaves the account restricted and forbids new action initialization or
dispatch until reconciliation. No automatic generation migration is provided.

## Acceptance, deployment and rollback

Independent reviewers must approve these new decisions before the corrected
production candidate and independent reference are compared. Required pure
cases include same cap/different exposure, same refs/different amount or kind,
normal and default same-time no-ops, changed/unchanged revision exhaustion,
deadline and interval equality, shared-policy conflict, scale mismatch and
unchanged inputs after rejected transitions. Unsupported durable ownership,
recovery and real dispatch must remain explicit rejections or external gates.

Deploy this commit as documentation only. D1 remains USD-only and pure; D2,
admission/withdrawal/transfer integration, global uniqueness, real ACK/outbox,
settlement and production remain disabled. Rollback reverts these new contract
files; no database migration, history rewrite or reinitialization is permitted.
Future executable deltas need their own source pins, independent review and
first-run evidence. No tests or target imports have run for this contract.
