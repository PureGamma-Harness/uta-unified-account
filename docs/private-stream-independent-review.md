# Independent private-stream contract review

Reviewed immutable design: `c68aabe82ce78ab10a3c886894ce8dc9952302d1`, based on
runtime `a35fd56fc98126b3e5cced8a459bd04ca580e537`. This is a static contract and
literal-vector review. No UTA module is imported by the reference checker; no
SQL, socket, provider fetch, listener or exchange operation was executed.

**Verdict: the narrow read-only product boundary is consistent with current
code; clarify the five conditions below before its affected runtime slices.**
The ten original frame examples, RFC accept, public synthetic HMAC and cursor
arithmetic agree. None of the thirty fixture requirements is a runtime pass.
This review does not approve a listener, production deployment or real funds.

## Existing-code boundary verified

`RequestAuthenticator.authenticate()` authenticates the exact raw request target
and empty body digest, then calls `NonceStore.consume()` before returning a
`Credential`. `consume()` records nonce and auth audit in the auth database's
own write transaction, samples time after acquiring the write lock and commits
before returning. A later scope/view/upgrade denial cannot unconsume that nonce.
The present return value omits key ID, identity, original key validity and the
consumption transaction's configuration revision. Looking up a possibly
replaced profile afterwards is insufficient to create the proposed binding.

The new binding must be returned from the exact key and committed auth receipt
used by that handshake. It is a trusted internal immutable identity record,
not a transferable client bearer token. Preserve `authenticate()` compatibility
for existing REST callers. Do not instantiate a new authenticator during each
read-only session check: its constructor calls `store.configure(profile)`.
A new checker needs an existing-file RO path and configuration/key checks
without that write path or nonce consumption. Persistent removal/revocation
must win over a retained in-memory profile. A higher unrelated profile revision
may preserve the same valid immutable key; a lower-than-observed revision or
clock is an integrity/unavailable result, not permission to use old state.

`ManagedAccountViews.read()` presently creates one RO transaction per call.
Its context and account projection therefore share a snapshot only within that
call. The original account event page filters account ID **before LIMIT** and
uses the shard-global event sequence. Its end page advances `next_after` to
`until`, including when no event belongs to the private account. The design's
normal gaps, snapshot watermark H, fixed catch-up range and empty checkpoint
rules agree. Do not call two public `read()` methods and label their union one
snapshot. New bounded helpers must share one connection and preserve REST
behavior rather than globally lowering its existing limits.

REST's generic permission helper allows an admin bypass. The new customer-only
listener must explicitly allow reader/trader and exact bound account before
account existence/view reads; funding, risk and admin do not gain access by
reusing that bypass. Default-off loopback TLS1.2+, no Bearer/Origin/cookies,
separate listener/process/worker slots and no financial command route are
consistent with the restricted first slice.

## Required clarifications

| ID | Affected slice | Concrete condition before implementation approval |
| --- | --- | --- |
| WS-R1 | Bounded context/start/page reader | Treat sizes as UTF-8 bytes and preflight **every** selected payload/config/market/text dependency in the same RO transaction before materializing it. |
| WS-R2 | Handshake parser | Require canonical Base64 encoding of the 16 decoded key bytes, or explicitly accept that raw key text is not uniquely bound by the signed challenge. The recommended policy is re-encode equality. |
| WS-R3 | Frame codec/close state | Specify valid incoming close-code set and directional outgoing rules, including reserved 1004 and client-only 1010; do not merely blacklist 1005/1006/1015. |
| WS-R4 | Listener/incremental receiver | Pin absolute post-upgrade header/control-payload assembly deadlines and guarantee a partial frame cannot block auth checks, ping/pong deadline or shutdown. |
| WS-R5 | Encoder/buffer | Define whether the 256-KiB frame and 512-KiB queue caps count the **whole wire frame**, including RFC headers, and enforce the chosen boundary before allocating/enqueuing. |

**WS-R1 details.** Current `_object()` compares `len(value)` to `4*1024*1024`.
That is a Python-character cap, not a four-MiB UTF-8 byte cap. A four-byte code
point makes the theoretical encoded upper bound sixteen MiB per selected row,
and a 200-row REST page can materialize much more than the stated byte budget.
This is a current resource-contract fact, not a claim of a tested exploit.
The proposed event `length(CAST(payload AS BLOB))` check is the correct direction.
Also bound the context path: `_context()` currently fetches complete policy,
risk-policy and market text before Python validation. Market's one-MiB byte
check runs **after** its SQL text has already been materialized. New helpers
cannot call that whole path first and then claim the smaller stream limits.
Counts, lengths, selected prefix, context and actual text must come from one
snapshot; all budget failures leave the durable cursor unchanged. Progress
handler/reader timeout does not establish an OS-I/O hard deadline.

**WS-R2 counterexample.** RFC's example key
`dGhlIHNhbXBsZSBub25jZQ==` and the noncanonical
`dGhlIHNhbXBsZSBub25jZR==` both pass Python's strict
`base64.b64decode(validate=True)` and decode to the same sixteen bytes.
They therefore give the same signed hex challenge. RFC accept hashes the
original header text, so their accepts differ. Requiring
`b64encode(decoded).decode('ascii') == header_value` makes that binding unique.
Perform this structural check before consuming a nonce. This is arithmetic
on public example bytes; no current WebSocket route was probed.

**WS-R3 details.** The review adds literal reserved-1004, one-byte-close,
nonminimal/oversized control and high-bit length examples. Client 1010 has a
valid interpretation but must not cause a server-generated 1010 merely by
blind echo; the design can specify a normal server 1000 response. Select and
document the accepted registry/profile range, including private 4000/4008;
reject invalid/reserved values with 1002. Validate header protocol before
applying the no-client-data policy: legal fragmented text can receive 1008,
while unexpected continuation, fragmented control, RSV/mask/minimal-length
violations receive 1002. These distinctions agree with the original examples.

**WS-R4 details.** A per-`recv` timeout that restarts on every byte permits an
arbitrarily slow partial control frame. Absolute monotonic deadlines must not
reset with another byte, unsolicited pong or nonmatching pong. Keep pending
ping identity/deadline until a matching pong, and keep the receiver incremental
and nonblocking so the 250-ms auth-check schedule and closing state continue.
Handshake's three seconds must likewise be total elapsed time. The one-second
revocation close and two-second shutdown remain unmeasured normal-operation
targets; the contract correctly discloses the final check-to-first-byte race
and that already-started/kernel-buffered bytes cannot be retracted.

**WS-R5 arithmetic.** A server text payload of at least 65,536 bytes uses a
10-byte RFC header. If the encoded **whole frame** cap is 262,144 bytes, the
largest JSON payload is 262,134 bytes. Two payloads of 262,144 each would instead
use 524,308 wire bytes, exceeding a strict 524,288-byte queue. Count queued and
in-progress buffers by actual encoded bytes. Two full allowed frames plus one
frame being encoded is 786,432 wire-buffer bytes per connection; this is not a
Python/SQLite/JSON/thread heap or 256-MiB process RSS proof. Apply caps during
encoding, not only after allocating a too-large serialized string.

## Independent literal results and limits

[The reference calculator](../evidence/runs/private-stream-independent-review/reference_vectors.py)
recalculates the standard accept `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=`, canonical raw
HMAC request and synthetic signature without importing production signing code.
It verifies the original stream ID from authority/path/device/inode/account.
The H=400 snapshot must catch commit 407 between the read and 101. Private events
407 and 413 are valid despite other-account sequence gaps; completed page 420
and empty page 425 advance the local cursor only after atomic client apply.
Duplicate replay yields two unique `(stream_id, sequence)` keys, and different
content under the same key must stop instead of silently replacing it.
Resume does not inject a new current account projection over the old baseline.
The `2**53+1` example demonstrates why binary-float parsing is not lossless.

Ten original client-frame vectors and five additional finite header/close
examples were checked with XOR, integer and UTF-8 arithmetic. The tiny reference
classifier only handles these finite vectors; it is **not** a production or
streaming codec. [Derived values](../evidence/runs/private-stream-independent-review/vector-results.json)
keep payload/control/RFC results and the Base64 alias. The thirty original cases
remain `NOT_RUN_REQUIREMENT`; permission, nonce uniqueness/durability, same-RO
snapshot, actual revocation and network/backpressure targets were not verified.

The reference calculator's first execution exposed an instrumentation error:
`dict.get()` eagerly evaluated a fallback `struct.pack(None)` despite an existing
reply. Its original source, fingerprint and actual error are retained. The
corrected calculator selects the branch before packing and then passes all
literal assertions. This is not evidence of a defect in the original design
or of a WebSocket runtime test having failed and been repaired.

## Minimal next slice and release conditions

After the relevant contract clarifications, the isolated pure frame codec and
bounded encoder/buffer may proceed first, with incremental partial-input/partial-
output state and explicit close states. That slice must have no listener,
financial import, public route or implicit writer/auth initialization. Actual
socketpair and temporary auth database testing require the integration owner's
separate GO; none is performed by this review. The session receipt/RO checker,
bounded context reader and final default-off TLS listener remain separate
reviewed slices. Existing REST signatures/roles/responses remain compatible.

A final connected implementation still needs real duplicate nonce/rotation,
key revoke/expiry/clock fault, state restart, source change, snapshot-to-H tail,
legitimate gap, oversized first event without skip, slow consumer/idle ping,
resource/descriptor cleanup and REST/writer isolation evidence. There is no
exactly-once network or full-account reducer claim; unknown events require
retention and explicit reconstruction. Design acceptance cannot transfer the
old runtime's full-suite, package or six/24-hour results to new code.

This review commit adds reports and a pure calculator only. It deploys nothing
and changes no schema, nonce, financial state or running source. Revert only
the added review files if needed, while retaining original requirements and
raw evidence. Production, PM, new products, throughput, HA and real-funds
approval all remain false.
