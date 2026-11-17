# Independent pure-codec review: c7 finding and 243 closure

Original runtime: `c7bbd41f1e4ea48961a59921826f80c585c34e6d`.
Fixed runtime: `24337ede7b07083c13c16736cb78628d6a01a7ec`.
Design baseline: c68 plus V2 `5348ab3`; design-finding closure `9bf26dd`.

**The mutable-header blocker is fixed in 243. No remaining correctness blocker
was identified in the reviewed pure-library scope.** This is an integration
review of an unused library, not a WebSocket endpoint, release qualification,
network deadline, authentication or real-funds approval. No socket, SQL, auth
store, exchange service, workload or running job was accessed.

## Original finding retained

The public `WireFrame` constructor in c7 freezes mutable payload backing, but
only compares header contents. An ordinary bytearray or memoryview header can
compare equal to the expected bytes while retaining an external mutable alias.
The default factories construct immutable bytes headers; this finding concerns
the explicitly public direct-construction path, not an exposed financial API.

Independent original observations show:

- Bytearray mutation changes validated `810178` to queued wire `8201797a78`.
  Actual frame size rises from3 to5 while queue accounting remains3; releasing
  that frame drives `application_wire_bytes` to **-2**.
- A memoryview header likewise permits opcode81 to become82 after construction.
  The original public `to_bytes()` also raises TypeError for that accepted
  header type because memoryview and bytes cannot be concatenated.

The first actual three-case run has two FAIL and one ERROR, with exact original
source/test hashes and complete logs. A second reference observation directly
compares header+payload bytes to reach the queued memoryview path despite that
existing `to_bytes()` error. On unchanged c7 it has three FAIL. The first result
was not replaced, and neither result is a deployed-service exploit claim.
[Original evidence](../evidence/runs/private-stream-codec-independent-review/README.md)
is committed in independent OWN `995cfbf`; the final review tree retains its
cherry-pick `9774c82`. Both versions of the original peer test are recoverable
from the retained source snapshots and their recorded hashes.

## Fix inspection and independent execution

243 adds `type(header) is bytes` immediately after opcode validation and **before
payload inspection or copying**. Nonbytes headers are rejected rather than
copied first. This closes bytearray/memoryview aliases and prevents custom
header comparison/length behavior from participating in frame validation. An
already supplied oversized exact bytes header is not copied; canonical header
equality rejects it. Payload byte-like views are bounded before copying into
immutable bytes. This is not a defense against arbitrary Python private-object
mutation, malicious subclasses or a hostile OS owner.

The peer cases accept either correct immutable preservation or explicit early
refusal; 243 refuses all three original mutable-header inputs. Additional
independent cases use literal RFC bytes and state expectations, without using
production predicates as an oracle. The final run uses the exact 243 module
SHA `15e1bd6cee256e976d86b7ef2f4c5c2357a84cb421e7e7784618f77c528e57a2`.
The same runtime bytes were checked before and after every run.

| Interpreter | Cases in this peer run | Actual wall seconds | Result |
| --- | ---: | ---: | --- |
| Python3.10 executable recorded in argv | author28 + independent13 = 41 | .114611 | PASS |
| Python3.12 executable recorded in argv | 41 | .114651 | PASS |
| Python3.13 executable recorded in argv | 41 | .114828 | PASS |

The full logs, actual UTC/argv, source/test hashes and constructor observations
are in [final-243](../evidence/runs/private-stream-codec-independent-review/final-243/summary.json).
ResourceWarning is treated as error; none was observed. All pure executions in
this review took less than five seconds in aggregate. No true wall-clock
network or scheduler behavior follows from these model-time assertions.

An intermediate 41-case discovery run is also retained. The test entrypoint
was then moved after the newly appended independent class so direct invocation
would collect those cases too; no runtime implementation changed. Historical
manifests/test-path hashes refer to their original recorded test versions,
not the later expanded peer file. Exact source snapshots resolve that identity
without editing the original manifests.

## Reviewed guarantees and limits

**Handshake arithmetic and frame classification.** The standard example accept
matches the independent literal. The noncanonical pad-bit alias and malformed
key/challenge inputs are rejected. This only binds canonical key/challenge
math; it authenticates no account and consumes no nonce. The V2 directional
close set is enforced, including client1010 parsed with normal1000 reply and
server1010 refused. Reserved1004, invalid close UTF-8, invalid high-bit lengths,
fragmented controls and unexpected continuation remain protocol errors before
the no-client-data application policy. The stream is not a generic client-data
WebSocket implementation.

**Input ownership and incremental progress.** A caller-owned1.05MiB block of
masked pings consumes exactly the first8 frames (56 bytes); excess stays with
the caller through `consumed`, and parser scratch remains at most139 bytes.
An independent small check measured this call's additional traced Python
allocation below64KiB, excluding the already allocated input. Every cut point
of nine distinct control frames preserves all nine in order across turns.
This does not bound caller input buffering, TLS/kernel memory or process RSS.
The parser checks protocol length fields before requesting any declared data
body; large/unsupported client-data payloads are not copied into its scratch.

**Deadlines are explicit model contracts.** Header expiry at500ms, control
expiry at1000ms and pending-pong expiry are absolute. Progress at499/999ms and
unsolicited pong do not move them; an exact-deadline match is late. The owner
must actually schedule these methods and enforce returned close/abort actions.
This module proves no250ms auth loop, network response time or OS-I/O recovery.
`peek()` starts the500ms write-attempt model budget; real send-result handling
belongs to a future nonblocking owner.

**Complete retained-frame accounting.** With two maximum frames queued, the
counter remains524288 after all but one byte of the active frame has been sent.
Closing discards only the unsent second frame, leaves the full262144 active
frame counted until release, then sends close at a frame boundary. It never
inserts close bytes into an active payload. The control reserve stays separate
at254 bytes even with the full application budget. These counters account for
buffer-owned complete frames, not just unsent tails. Caller-retained output
views and independently held frames can keep immutable bytes alive outside the
buffer; they are not a total-process-memory proof and must be released by the
future owner.

**Partial-output tokens and backpressure.** A forged object with copied fields,
a superseded `peek` result or a duplicate `advance` cannot advance the current
wire offset. Only the latest issued object and valid count can progress.
The full application queue rejects before requesting even the first chunk from
an upstream iterator. An already allocated1MiB chunk is rejected before another
MiB copy; a traced finite check stays below64KiB of additional Python allocation.
That does not claim the upstream serializer avoided constructing the chunk.
The library does not serialize JSON: a later bounded serializer must precheck
or segment oversized scalar strings rather than treating `iterencode()` as an
upstream allocation bound. UTF-8 validation, bounded builder freezing and
explicit `to_bytes()` copies have their own bounded temporary allocations.
Wire budgets786686 bytes with controls remain distinct from heap/RSS limits.

Static inspection finds only stdlib imports in the new module (`base64`,
`codecs`, `collections`, `dataclasses`, `hashlib`, `re`, `struct`). No existing
UTA module imports or references this library, and the only UTA path differing
from a35 is the new codec module. Existing auth, gateway, reader, writer, money,
matching and observer implementation files remain unchanged.

## Integration decision and remaining gates

The corrected **unused pure library** may proceed to ordinary source
integration/release validation under the integration owner's approval. Keep
c7's historical failure and 243's limited pass identities separate. The original
30+28 design cases still contain many `NOT_RUN_REQUIREMENT` contracts: HMAC/
nonce commit and session receipt, persistent revocation/rotation, same-RO
snapshot H and byte preflight, real socket/TLS/partial I/O, actual bounded lanes,
reader fairness/backpressure, source replacement and writer/REST isolation are
not delivered by this library.

The future bounded event reader must also preserve the byte-cut cursor rule
already recorded in the V2 closure: two64KiB selected rows do not justify jumping
to H when a further eligible row exists below H. No SQL reader implementation
was tested here. There is no route, listener, auth-binding capability or
financial action in this change, and this review grants none.

Adding a new module changes release artifact identity even when no existing
service imports it. The integrated exact source still needs its own complete
unit/CI/actual package and installation checks. M2, previous package results and
ongoing six/24-hour jobs cannot qualify different new source. Production,
capacity, replicated/AZ recovery and real-funds approval remain false.

Deployment here is source integration only; rollback removes the unused library
and its tests/docs in a later checkout. It never edits an active job, resets a
cursor/nonce, releases financial reservations or reverts confirmed fills.
Preserve the original counterexample and all scoped validation records.
