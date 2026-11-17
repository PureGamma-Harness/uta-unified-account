# Independent H0 design review — refinement required, no execution approval

Reviewed author plan `431225d01439cba1a4acce6529e35368eac391df`, based on frozen dbc93e5 and PR18 `01c332375d9a5463ca95d8e743ff5083b121982e`. This review concerns the proposed H0 authentication acceptance component only. It does not qualify final candidate909, implement HMAC lending, approve SQL execution or authorize a public route.

The architecture can support a small fresh-AuthDB component after the mandatory rules in [required-refinement.json](required-refinement.json) are made normative. The original plan and its thirty `NOT_RUN` cases remain unchanged. The root must separately decide the concrete implementation and execution scope; no parent action approval is inherited by this review.

## Code facts independently checked

All fourteen declared input hashes match the retained Git blobs. Existing `RequestAuthenticator.authenticate` calls `NonceStore.consume` once and returns `Credential`; neither `consume` nor `_audit` returns a durable acceptance or audit sequence. The old `auth_keys` row contains only key ID, identity and revoked status. The existing `_SignedDurableHandler._principal` already authenticates, while PR18 `CreditHmacSource.issue` authenticates again if naively used as its route. PR18's audit sequence/profile revision/credential epoch remain null, `financial_authorized=false` and `revocation_barrier=NO_GO`. Its candidate evidence cannot be promoted by relabeling it.

The ordinary gateway's role helper permits admin bypass. H0 needs an exact funding/operation/account/asset grant rule with no such bypass. Current effective query authorization is separate from historical borrow permission. A copied JSON receipt or a receipt issued before revocation cannot authorize current lookup or future financial execution.

## Required policy closure

The plan's HC-04 permits a valid-auth nonce to be consumed, while HC-07 requires consumption and a committed denial audit. That is an implementation ambiguity, not an observed production vulnerability. Fix a deterministic table: after valid MAC, active key/time and fresh-nonce checks, business/input/role/grant/CID rejection consumes that nonce with a denial audit and creates no accepted receipt or reservation. Bad signature/header requests do not consume. Key/time/replay/quota refusals do not insert a new nonce. When clock, storage or audit capacity prevents a reliable commit, return503 UNKNOWN with no success handle; do not claim a403 denial was durably audited.

A retry transport acceptance must remain distinct from the immutable first business acceptance. Same logical CID and content under a new nonce may return a passive reference to the original identity. It must not replace the original key/grant/epoch or create an execution handle under a newly granted key. Different kind/content conflicts under the original key; kind, epoch and payload hash are not business-key dimensions. Expired nonces or capacity pressure never erase original business reservations.

H0 requires a real current-authorized AuthDB original-CID lookup to resolve an auth COMMIT reply loss. The lookup uses fresh authentication and effective `credit.read` permission, returns passive evidence only, and has no financial database or HTTP dependency. Its result does not turn a reader into the historical borrower. Without that API, the proposed UNKNOWN protocol is incomplete in H0.

Use a fresh explicit auth format with exact MAIN schema/PK/FK/CHECK/immutable guards, actual nonsecret key metadata and durable grant identities/epochs. Checking only table names or column names is insufficient. Never add new tables to an existing format1 database and call it a qualified new format. Require an ordinary format1 positive control and actual old-reader refusal of the new format before component acceptance. Unknown, moved, corrupt or missing authority state is not silently reinitialized or repaired.

The accepted nonce, its actual audit sequence/revision, actual locked key/grant state, auth-only receipt and first business reservation share one AuthDB COMMIT. Read those values from the held transaction, not later mutable profile state or a capture timestamp. Issue the local opaque handle only after successful actual COMMIT return. A committed row plus lost response stays queryable; it does not justify constructing a success object from an exception.

The shared verification refactor must preserve old `authenticate` behavior and return type. A client cannot supply a principal, authenticator, SQL callback, epoch integer or imported receipt as authority. Keep real PID/current Thread object/issuer registration binding and check fork identity before taking a potentially inherited lock. Follow a fixed profile-lock→AuthDB order, or release a profile snapshot before acquiring AuthDB and validate actual stored identity inside it. Never reacquire the authenticator lock while holding AuthDB. H0 creates no cross-database execution barrier and grants no H1/H2 approval.

## Independent pure verification

The [checker](check_plan.py) ran once using the exact [command and captures](execution-record.json). Its [first output](first-check.json) contains **710 successful Git/hash/AST/logical checks**, including a finite model with **76 states and332 transitions**. No production module, oracle, SQL, database, native guard, TLS server, unit suite or benchmark was imported or executed. Empty original stderr is preserved. The original thirty cases remain `NOT_RUN`; twelve additional H0 cases are proposed, also `NOT_RUN`.

The logical model assumes three finite grant identities, two payload identities, permanent revoked-grant tombstones, no reservation pruning and idealized atomic steps. It proves only its declared first-reservation identity and tombstone invariants. An intentionally unsafe rebind has a three-action counterexample: accept under grant0, revoke grant0, then overwrite the same-CID reservation with active grant1. That illustrates a policy hazard; it is not an exploit of an existing implementation or evidence of a real financial effect. Actual SQLite atomicity, concurrency, crash, handle and full source behavior still require separate execution and independent review.

Internal recorded UTC is17:07:55.048596–17:07:55.130431 and process CPU is30,172,177ns. The original tool-reported wall is0.014157291s, shorter than that internal span. Both are retained without a replacement run. No independent outer monotonic interval was recorded, so this review makes no latency or complete outer-timing claim. The static/model result does not depend on such a claim.

## Implementation boundary and recovery

After the addendum is reviewed, the root may consider a new, default-disabled H0 branch containing only a fresh auth authority, shared authentication core, exact grants, opaque auth-only receipts and original-CID auth lookup. Any proposed temporary private-DB execution remains subject to the root's concrete scope and bounds. H0 must not create financial source/PENDING/intent/postings, attach to V2 as another source kind, construct a listener or change READY/public501.

This deliverable is documentation and a pure checker. It has no deployment, data migration or runtime rollback requirement. Omit its branch to roll it back. Future accepted auth reservations survive reply loss and process restart; unresolved records cannot expire into absence. Cross-epoch retirement, backup anti-rollback, distributed ordering, storage-loss recovery, HA, throughput and real-funds approval remain unproven. Keep the final909 source and every original job, result and private authority unchanged.
