# HMAC source candidate component: actual small synthetic observations

No financial source COMMIT, owner, borrower execution, endpoint or CLI was
implemented or enabled. The default-disabled component uses actual existing
`NonceStore` / private `load_profile` / `RequestAuthenticator.authenticate`
against self-created temporary databases. All random HMAC keys and private
keyfiles remained inside mode-0700 temporary directories, removed after tests;
no keyfile, secret, live raw nonce or signature is retained here.

Base: `8b7f544fcbdfd540d43de1d6560022c6ebbd3799`.
Contract-first commit: `1f8b52b79da65e76bed1d599151d52d84f37cc53`.
Per-file SHA256, exact commands, original output, exit codes and UTC checkpoints
are in each metadata/stdout/stderr triplet. Every batch had timeout30s, CPU3;
final stdout records the real child PID, runtime and affinity `[3]`.

| Original run | Actual tests/time | Process UTC start/end | Exit |
| --- | --- | --- | --- |
| initial, Python3.12.14 | 14 / 0.213s | 2026-11-17T13:53:31.749505+00:00 / 13:53:32.099600+00:00 | 0 |
| python312, Python3.12.14 | 16 / 0.252s | 2026-11-17T13:54:47.338990+00:00 / 13:54:47.736497+00:00 | 0 |
| python313, Python3.13.5 | 16 / 0.307s | 2026-11-17T13:54:47.740640+00:00 / 13:54:48.161240+00:00 | 0 |

The initial run is preserved even though two additional boundary tests were
added afterward. Its source hashes identify its earlier exact test bytes. The
final two runs use identical component and test source hashes, with
ResourceWarning treated as an error. No observed failure was discarded.

Observed: actual private loader/nonce COMMIT/audit linkage; key roles, explicit
local allowlist, tenant/audience/producer/account isolation; wrong body/MAC,
nonce replay, time window, duplicate header, expiry, real rotation and durable
revocation through a stale authenticator; strict signed JSON/amounts; opaque
receipt reconstruction/copy/serialization rejection; actual thread/fork and
issuer isolation; stable same-CID normalized-business retry; bounded registry
and missing authDB/private-file refusal. A role denial consumes the nonce yet
creates no candidate. A new boot creates a different local candidate: this is
explicit evidence that the component does not prove persistent first-source
identity or permit historical CID backfill.

Outstanding: actual producer source+PENDING SQL/COMMIT, durable historical-CID
lookup, native consumer, future dedicated HMAC capability/schema, accepted
auth-audit sequence/profile-revision/credential epoch, and a linearizable
cross-authDB/financialDB revoke/execute barrier. The selected revoke-before-
execution policy remains **NO_GO** without that barrier. A receipt export
always states `financial_authorized=false` and `revocation_barrier=NO_GO`.

This is a component test record, not actual V2 positive financial capture,
production approval, capacity, multi-host consensus or anti-rollback proof.
Rollback is a code revert; this slice installs no financial schema or history.
