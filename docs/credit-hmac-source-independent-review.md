# Independent HMAC source-candidate review: 03b85ad

Reviewed component: `03b85adbf8dafbeae8914db6d9b668e5c1fffe92`, following
contract-first `1f8b52b79da65e76bed1d599151d52d84f37cc53` on frozen base
`8b7f544fcbdfd540d43de1d6560022c6ebbd3799`.

**Scoped verdict: no blocker identified for this unwired, default-disabled
source-candidate component. Loan integration and cross-database execution
remain NO_GO.** This is not a financial permission, native-format approval,
source COMMIT, endpoint delivery, security scan or production qualification.
The author's tree, original jobs, financial databases and frozen candidates
were not changed or accessed by this independent review.

## Actual independent verification

The original sixteen tests ran once on CPython3.10.22, CPU3, with
ResourceWarning fatal: sixteen passed in0.335 seconds; child execution and
capture took0.467349 seconds, below its30-second timeout. Component, test,
request-signing, public vector and contract source hashes were identical
before/after. The original tests actually create their own private AuthDBs and
random keyfiles and exercise the existing verifier, including a separately
owned fork/thread refusal. They start no financial service, endpoint or
network listener. The author's earlier14-case and final16-case3.12/3.13
records remain separate; this is not a claim to repeat a complete release.

One additional independent case ran once on Python3.10/CPU3:1 PASS,
0.171282 seconds including capture. It calls through the actual AuthDB
transaction, lets it COMMIT, then injects loss of the response. The real
NonceStore reports signing_store_unavailable. Independent read-only queries
of that same newly owned AuthDB confirm the nonce and nonce_consumed audit
hash persisted, while the component minted neither a command candidate nor
an opaque handle. Repeating the original nonce is rejected as replay. A new
nonce with the same business CID is verified afresh and can create only a
local candidate with financial_authorized=false and revocation_barrier=NO_GO.
There are still no financial source/inbox tables or source COMMIT.

The fault injection wraps a real transaction's return after successful
commit; it does not replace a verifier result with a caller-asserted success.
Only private temporary authentication SQL was used. No raw nonce, signature,
secret, keyfile, authentication database or financial data is archived.
The fixture's hash comparison remains an in-process assertion; public raw
output contains only test names/results. Original16 tests were not rerun to
produce this additional case.

## Authentication and metadata contract

Disabled construction returns credit_source_disabled before opening/creating
an auth database. Explicit enablement is trusted local configuration. Enabled
construction opens an existing private NonceStore, checks tenant and producer
binding, loads a private regular service-user keyfile and uses the actual
RequestAuthenticator. Its existing constructor/configure path can persist
profile registration/rotation in the AuthDB. Thus disabled capture is not a
claim that enabled construction is AuthDB-read-only. No financial schema or
financial role is touched.

Headers are copied before real verification and metadata extraction. Duplicate
authentication headers, wrong exact method/path/body/MAC, invalid tenant or
audience, malformed canonical signing fields, expired/revoked keys and stale
timestamps fail through the existing signing protocol. Authentication
requires bounded exact bytes and commits the actual hashed nonce/audit before
returning the authenticated principal. No caller-supplied principal, callback
verifier, JSON claim or fabricated Credential can mint the opaque handle.

The subsequent component input is exactly POST to its specified account borrow
path, not an installed endpoint. Strict JSON accepts only CID, BTC asset and
canonicalizable positive decimal-string amount with at most8 fractional
digits and fewer than10^38 minor units. Numeric/boolean amounts, unknown or
duplicate fields and unsupported routes/products are rejected. Canonical
business payload includes account/asset/normalized amount, with CID separate;
auth nonce/time/key do not change its business identity.

Actual account-scoped funding role and an exact server-configured key/account
allowlist are both required for capture. Admin, reader, trader and risk have
no implicit capture or loan privilege. Funding here is source capture only,
not borrower permission. A role/body/route denial after authentication may
leave the nonce consumed but creates no candidate, as distinct from MAC
rejection before nonce consumption. Capacity can also fail before or after
authentication depending on which bounded registry is full; no ACK or source
acceptance is invented from either error.

Metadata is computed from the same frozen authenticated headers, exact body
bytes and actual principal used by the real verifier. It exposes permitted
business fields and body/request/nonce hashes, key/role/account/tenant/
audience/producer identities, signed time and post-return capture UTC.
Capture UTC is not the nonce COMMIT timestamp. It exports no signing secret,
raw signature, live nonce, raw body or private file path. The public static
canonical vector's fixed example nonce is test input, not a live credential.

The public verifier returns Credential without an accepted audit sequence,
profile revision, key fingerprint or atomic execution epoch. The component
leaves accepted_profile_revision, auth_audit_sequence and credential_epoch
unavailable rather than inferring them from profile file mtime, a later
configuration read or the capture clock.

## Opaque handles and local first-candidate scope

Only an exact registered _Receipt instance issued by this issuer validates.
JSON/field reconstruction, new same-class objects, copying/pickling and a
different issuer cannot substitute for registry identity. Inspection binds
exact account/CID/canonical payload. PID is checked before acquiring an
inherited lock after fork; handles also bind the actual creating Thread
object, avoiding recyclable numeric thread IDs. Per-issuer random boot/source
identity and distinct registries prevent imported handles from proving a
previous issuer's state.

These are fixed-trusted-binary remote/field-reconstruction boundaries. They
do not defend against arbitrary same-process reflection, monkeypatching or
host code execution. Receipt export is immutable evidence and cannot be
reimported as a handle or elevated into financial authorization.

One local first candidate is retained per CID. After fresh authentication,
same-business retries can get a new thread-bound handle to that original
local candidate; different account/content conflicts. Releasing a handle
does not evict its first candidate. Registry exhaustion fails closed. A new
issuer/restart has no durable first-CID knowledge and creates a different
local reference. None of this proves the first source+PENDING producer
COMMIT; the component has no such transaction or lookup.

## Revocation, unknown outcomes and remaining NO_GO

Actual profile rotation and permanent AuthDB revocation can reject a new
authentication through a stale authenticator. An already issued candidate is
historical evidence and may still be inspected; it remains financially false.
Inspection is a trusted local evidence API, not a new remote query permission
for a revoked credential.

No implemented protocol linearizes key/grant revocation with financial
execution across AuthDB and financial DB. An earlier signature or a fresh
pre-COMMIT key read cannot close that race. Accepted credential/audit epoch
proof is also missing. The chosen revoke-before-execution policy therefore
remains NO_GO; pending HMAC-origin loans cannot execute through this component.

Nonce COMMIT, future source+PENDING producer COMMIT and future financial
effects/intent/journal/decision/terminal COMMIT are separate obligations.
Unknown auth response cannot prove absence or source acceptance. A future
consumer must use an independently authorized new-nonce original-account/CID
lookup to resolve persistent outcomes before considering a new first source;
it must never backfill an old CID, replace an UNKNOWN source or create new
debt/IDs from an exception. This slice implements none of that consumer SQL,
HMAC native capability, execution barrier or financial permission.

The existing synthetic_local native mode and managed borrow501 policy remain
unchanged. Rollback is code-only for this unwired slice. A future persisted
mode will require reviewed forward recovery preserving all source/CID and
committed financial obligations. No real-funds or production GO is granted.

[Exact commands, hashes and unedited independent raw results](../evidence/runs/credit-hmac-source-independent-review/manifest.json)
bind this report to the reviewed source. Temporary AuthDB verification is not
financial SQL verification, transport acceptance, capacity or long stability.
