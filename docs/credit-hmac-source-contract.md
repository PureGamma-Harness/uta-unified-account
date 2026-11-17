# Unwired credit HMAC first-source candidate contract

Checkpoint based on immutable `8b7f544fcbdfd540d43de1d6560022c6ebbd3799`.
This is an independent, default-disabled authentication evidence component. It
does not enable HTTP/CLI borrowing, grant a writer, install SQL, change an active
capability, or establish real-funds readiness. Public/CLI new managed borrow
continues to return 501. The existing V2 source kind remains `synthetic_local`.
Future HMAC ingestion needs a separately reviewed capability, schema and phase;
these candidate bytes must never be re-labelled as a synthetic V2 receipt.

Reviewed upstream contracts, using committed objects rather than live files:

- `634b3f1c31ccee223e09a3861834c9a32e374327:docs/credit-internal-v2-contract.md`
- `b510d18cb4ea6ab6213374884fa40a2f7754977e:docs/credit-v2-payload-contract.md`
- `59cf237917b7e3a9e44e1aaeabb6dd9ac148c54d:uta/credit_native_v2.py`

## Actual authentication and explicit source-capture scope

There is no `uta/auth.py` or `AuthStore` at this base. Actual existing public
authentication consists of `NonceStore`, `load_profile`, and
`RequestAuthenticator.authenticate` in `uta.request_signing`. The component must
open an already initialized private auth database and private keyfile, check the
configured producer binding and tenant, and call that real public verification
path. No JSON principal, caller-constructed `Credential`, `SigningKey`, public
dataclass, callback verifier, or claimed signature result may mint a receipt.
Construction is disabled unless explicitly opted in by trusted local code.

The candidate path is exactly `POST /v2/accounts/{account}/borrow`, with signed
exact UTF-8 body bytes and strict JSON fields `command_id`, `asset`, `amount`.
This describes a component input, not an installed route. Amount is positive
BTC, at most eight fractional digits and less than 10^38 minor units. The
canonical business payload is the sorted compact JSON object
`{account_id,asset,amount}`, with normalized decimal amount; CID is separate.
Authentication nonce/time/key never enter the business payload hash. Unknown
fields, duplicate JSON keys, float metadata, Unicode amounts and malformed
identities fail closed.

Source capture requires both an actual authenticated, account-scoped `funding`
principal and an explicit local allowlist of exact `(key_id, account_id)` grants.
A role alone grants no borrowing. Reader, trader, risk and admin keys have no
implicit borrowing permission. These local grants allow only candidate capture;
they are not the future borrower/financial authorization policy or its epoch.
The latter remains a separate missing capability. No remote input configures
grants. Cross-tenant/audience and cross-account signatures are rejected.

## Opaque receipt and first-reference rules

Only a successful real `authenticate` call, including durable nonce COMMIT,
followed by strict role/scope/payload checks may issue a receipt. Receipt
instances are opaque objects tracked by exact object identity in the issuing
registry. A copied object, object reconstructed with the same fields, JSON,
another issuer's receipt, another thread, a forked process or a restarted boot
cannot pass the registry check. Bind process PID, the live `current_thread()`
object (not a recyclable thread integer), and a random per-issuer boot identity.
This assumes a fixed trusted Python service binary. It protects the remote
customer JSON/field-reconstruction boundary; it does not protect from arbitrary
same-process Python reflection, monkeypatching, code execution or debugger use.

Each issuer keeps one immutable first candidate per CID, bound to tenant,
audience, producer binding, account and canonical business payload. A successful
new-nonce retry with identical business content returns a new thread-bound
opaque handle to that first candidate, retaining its original source reference
and first authentication evidence. Reuse with a different account/content is
an idempotency conflict. Receipt export verifies caller-supplied account, CID
and canonical business payload. Exported data is inspectable evidence, never
an input accepted by receipt validation. A bounded in-memory registry fails
closed at capacity; it never evicts first identities silently. There is no
persistent uniqueness claim across component restarts.

“First source” means the first actual producer COMMIT containing source+PENDING,
not the first HTTP authentication or the component's first local candidate.
The local reference is only a prospective candidate identity. It proves neither
producer acceptance nor a durable source. The future consumer must establish
the persisted first source through the actual producer transaction and lookup.

Retain evidence version `credit-hmac-source-candidate-v1`, unique source
reference, tenant, audience, producer binding, key ID, actual role/key-account,
requested account/CID/kind, canonical business payload and hash, first request
method/raw path, exact body SHA256, canonical signed-request SHA256, nonce
SHA256 and signed timestamp. Also record actual UTC candidate-capture time and
issuer boot identity/PID. Do not retain secret, raw nonce, signature, raw body,
keyfile path, or auth database path. Capture time is after auth return, not the
nonce transaction's server time, producer accepted time, or physical COMMIT time.

Existing public `authenticate` returns only `Credential`. It does not expose
the successful audit sequence, accepted profile revision, key fingerprint or
an atomic credential epoch. The component must leave those proofs unavailable,
not infer them from a mutable profile/snapshot or claim a post-return clock is
the original authentication COMMIT clock.

## Revocation and the two-database NO_GO

Chosen future policy: key/grant revocation accepted before a loan's financial
execution must prevent that still-pending loan from executing. A key's prior
signature acceptance is historical evidence and must not disappear, but is not
a perpetual execution permission. Already committed outcomes are immutable;
later revocation does not erase or re-execute them. An active independently
authorized querying credential uses a fresh nonce to query the original
account/CID. A revoked credential is not entitled to query merely because it
submitted the command.

**NO_GO: no implemented cross-authDB/financialDB linearizable revocation or
grant-epoch barrier exists.** Re-reading a key before the financial COMMIT,
copying revision fields or storing a timestamp cannot close the revoke/execute
race. The public authentication API also lacks atomic accepted-epoch/audit-ID
evidence. The component therefore has no financial authorization method. A
future consumer must prove a linearization protocol, crash recovery and unknown
outcomes for revocation, producer acceptance and financial execution before
using this source mode. Until then, pending HMAC borrowing cannot execute.

Auth nonce COMMIT is first and separate. A future producer must insert immutable
first-source plus PENDING in one producer COMMIT on the financial database.
Later financial execution references that original source, with effects,
intent, journal, decision and terminal in its own financial COMMIT. It must not
claim all three transactions were one COMMIT. Failure after auth COMMIT may
leave no inbox/source; failure near either later COMMIT can be UNKNOWN.

The future consumer must look up original account/CID before considering a new
source. Existing same-business PENDING/terminal retries preserve the persisted
first source and return the original result; conflicting content rejects.
An old CID with no historical first source is never backfilled from a new
receipt. A component restart cannot distinguish an old CID: only the actual
financial inbox/source lookup can enforce that requirement. Unknown COMMIT is
resolved by authorized same-account/same-CID lookup with a new nonce; never
mint a replacement CID, source, debt or success from an exception. This slice
implements none of that source SQL or consumer logic.
After authentication succeeded but producer acceptance failed or is unknown,
the new-nonce/same-CID retry first queries original durable state. Only confirmed
absence permits a new first-source producer transaction. UNKNOWN never means
absence and never permits overwriting an existing source.

## Reviewable test vectors and evidence

`tests/vectors/credit-hmac-source-v1.json` fixes only nonsecret canonical input
and independent SHA256 expectations. Runtime HMAC verification uses fresh random
test keys in a private temporary directory and the real private-file loader and
auth database APIs. No secret or live signature is archived. Tests must cover
real role/account/tenant rejection, wrong body/MAC, duplicate nonce, timestamp
expiry, actual rotation and revocation observed by an old process profile,
opaque-object forgery/copy, issuer/thread/fork/boot isolation, same-CID retry and
business conflict, capacity, and default-disabled behavior.

Record exact source hashes, command, CPU affinity, actual UTC start/end, exit
code and unedited stdout/stderr. Preserve failed/unknown observations honestly.
Only small self-created temporary DB tests are authorized: CPU3/4, each batch
at most 30 seconds, no network, stress, long jobs or existing financial jobs SQL.
No actual V2 positive capture or production approval follows from these tests.

Rollback for this unwired component is a code revert. Since it installs no SQL,
it requires no financial downgrade or mutation. Any future persisted HMAC mode
will require reviewed forward recovery preserving the original source/CID and
all committed effects; deleting markers or historical evidence is forbidden.
