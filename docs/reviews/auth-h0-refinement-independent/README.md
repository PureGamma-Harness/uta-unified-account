# Independent fixed39 H0 refinement review

Reviewed fixed author OWN `39cddde7159fb0307aba97c4fa355cd52a807b1b`, containing the three H0 refinement documents and the exact cherry-picked earlier independent review. The original431 plan documents and all thirty original cases remain byte-identical. The twelve new H0 cases remain `NOT_RUN`.

**R1–R8 are normatively closed for the H0 design, subject to implementation constraints A/B/C below.** The root may consider a separately scoped default-disabled H0 implementation and short private AuthDB component validation. This review itself authorizes no runtime or SQL operation. It accepts no schema execution, installed product, financial permission, production release or final909 qualification.

## Closed design requirements

| Rule | Fixed normative behavior |
| --- | --- |
| R1 shared core | One private real MAC/header and held-connection nonce/time core, legacy format1 signature and Credential return preserved; no arbitrary principal/authenticator/SQL callback injection. New store does not enter legacy factory as a permissive subclass. |
| R2 deterministic nonce refusal | A core-valid fresh nonce and its business/input/permission/CID denial audit share COMMIT. Authentication/key/time/replay/quota refusal does not insert a new nonce. Audit or commit inability yields503 UNKNOWN without a fabricated successful handle or durable403 claim. |
| R3 fresh exact schema | Auth format2 differs from old auth format1 and future financial HMAC3. Exact MAIN schema/constraints/FK/PK/immutable guards, private identity and full checks are mandatory. Existing format1 is not upgraded or repaired. Real old positives and old-reader prewrite rejection remain required. |
| R4 actual accepted evidence | Nonce, request audit, actual locked revision/epoch and first acceptance share one AuthDB transaction. Only actual successful COMMIT return permits an opaque observation; no physical COMMIT timestamp is invented. |
| R5 immutable first identity | Domain/tenant/account/business CID is the stable key. The first row is its permanent reservation and cannot update/delete/replace or rebind after revocation. Same-content retry needs current read permission and yields only passive original reference; changed kind/content conflicts. |
| R6 query and handle boundary | An actual signed AuthDB lookup requires current same-account reader/funding plus exact `credit.read`. Handles are issuer/PID/current Thread object registered; exported JSON cannot be imported. First/query observations both have financial/source-delivery/execution authorization false. |
| R7 capacity and retention | Explicit nonce/audit/handle query reserves and control audit reserve, counts under BEGIN IMMEDIATE, no second acceptance allocation for old CID, no expiry or pressure pruning of accepted/grant/audit history. No guaranteed availability after query/control budgets themselves are exhausted. |
| R8 ordering | Profile/grant mutation and acceptance share the AuthDB writer transaction. Fixed profile-lock order or released immutable snapshot; no DB→profile lock acquisition, no future cross-DB financial barrier claimed. |

The fixed API distinguishes explicit offline fresh initialization from a disabled ingress constructor that opens no files. H0 recognizes BORROW/REPAY only as authentication intent observations. It creates no financial source, PENDING, native capability, loan, repayment, risk admission, listener or READY transition. `found=false` on an AuthDB lookup is not proof of financial or old-epoch absence.

## Required implementation clarifications A/B/C

**A — classify before effective quota selection.** The draft states core quota checks before business/grant evaluation, while protected query eligibility depends on actual current `credit.read`, exact route and an existing same-business CID. On the same held connection, perform shared key/time/replay/prune prechecks, then a read-only authoritative classifier, then shared nonce count/insert using that class, then business verdict plus one request audit. The classifier gives no authority and makes no early business rejection. Keep format1's original order and error semantics. The root and author received this requirement before implementation.

**B — new key configuration cannot reuse legacy UPSERT.** The proposed new `auth_keys_no_replace BEFORE INSERT` guard sees existing key identity before an UPSERT update path. New format2 configuration must explicitly SELECT and UPDATE a retained key identity, or INSERT a new key. The old format1 configuration remains unchanged. This is a consequence of the proposed guard and required DML protocol, not evidence that the DDL has run.

**C — preserve genuine query handle capacity.** Before AuthDB, an unverified path does not establish query permission. Refusing every request when normal224 handle capacity is full defeats the reserved32 query handles; allocating reserve on an unauthenticated GET path lets it be consumed without permission. Use bounded non-authority intake separate from protected handles, or an equivalent demonstrable protocol. After actual DB classification, a short registry lock reserves the proper handle class; registry locks never span authentication or DB acquisition. Fill after actual successful COMMIT and release failed reservations. H0-I10 must actually test normal-full→permitted-query success and unauthorized-query→no reserved handle use.

These are mandatory details of the narrow design, recorded in [design-decision.json](design-decision.json). They are not new financial scope. The author's implementation must retain the fixed39 documents and record its clarification separately; an implementation or test failure stays its original outcome.

## Independent checks and their limits

The [checker](check_refinement.py) ran once with the exact [execution record](execution-record.json). First stdout and empty stderr are retained. It completed **1,612 successful pure checks**, including **1,536 finite quota-boundary combinations**. External monotonic interval was119,364,394ns, including child completion and output-file closing; final execution-record serialization follows that endpoint. This is a small file/model run, not latency or throughput acceptance.

The checker independently verifies the three fixed input hashes, original plan/review byte preservation, formats, permissions, immutable identity declarations, all NOT_RUN flags, explicit capacity arithmetic, shared-core/locking declarations and exact text references to required guards. It enumerates **34 explicitly named CREATE objects, including seven MAIN tables**, by regular-expression text scanning. It does not parse SQL grammar, call SQLite or verify implicit autoindexes. The complete actual schema object inventory remains a future dynamic obligation; “34” must not be represented as a measured SQLite catalogue count.

The quota model assumes already validated current key/time, authoritative same-connection classification and idealized integer counts. It checks normal/query thresholds at declared boundaries, including ordinary-full cases, and denies reserved admission without current read permission. It proves no SQLite serialization, actual registry protocol, file durability, thread scheduling, crash or revoke behavior. It does not replace actual H0-I01–I12.

No product import, SQL parser, database open, native guard, listener, TLS, unit suite, build, package, benchmark or push occurred. The checker was uncommitted at execution; its exact SHA is preserved and its final committed bytes match. The final909 frozen source and original jobs/results/private state were not modified.

## Suggested bounded implementation and rollback boundary

Use a separate root-specified branch from exact909, touching only the shared authentication core, the new H0 auth module and scoped authentication tests. Preserve the old format1 API and PR18 candidate-only behavior. Actual temporary-AuthDB tests require the root's separately issued bounds, synthetic private keyfiles and first-outcome retention. Genuine authentication, audit/nonce atomicity, accepted-row/hash/permission equality, old-reader refusal, competing grant changes, commit reply loss and current-authorized original-CID recovery are still unverified.

This review changes documents only and needs no deployment or migration. Omit its review branch to roll it back. Once a future H0 authority has retained accepted identities or tombstones, never delete/reinitialize/downgrade it to force a retry. H0 knows no financial outcome. Future HMAC3, cross-epoch retirement, anti-rollback, storage-loss recovery, capacity, HA and real-funds approval remain open.
