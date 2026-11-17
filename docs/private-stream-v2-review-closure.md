# Private-stream V2: independent design-finding closure

Reviewed amendment: `5348ab36d9aa254428c032e7523aa77ae8bed2d2`.
Original design: `c68aabe82ce78ab10a3c886894ce8dc9952302d1`.
Original independent findings: `f7a86b5a7a53476fb277272b0d5cb7c679d73540`.

**WS-R1–R5 are closed at the design level for the stated restricted profile.**
The amendment makes the required policy and ordering choices explicit. This
adds no runtime qualification: nonce/session authority, same-RO data helpers,
listener scheduling, TLS, storage and memory limits remain unimplemented and
unverified here. No SQL, socket, provider request or workload was executed.
The original findings and their evidence remain unchanged in their original
files rather than being rewritten as though no gap existed.

## Closure mapping

| Finding | New binding requirement | Independent result | Still required in code |
| --- | --- | --- | --- |
| WS-R1 | Current policy, risk-policy, current market, referenced archive and context/identity/guard text all require typed BLOB-byte preflight in the same RO snapshot before Python text materialization or decoding. | The old character/UTF-8 example is correct; oversized policy/current/archive and non-TEXT cases imply refusal without cursor advance. The existing unbounded `_context()` is explicitly excluded from the new path. | Exact bounded SQL shapes, complete dependency inventory, lengths/counts/rows from one snapshot, source-change and concurrent-write tests; no SQLite execution was performed. |
| WS-R2 | Strict decode plus canonical Base64 re-encode equality, then decoded challenge equality; failed structure precedes nonce consumption. | The canonical and alias header decode equally but produce different RFC accepts. Re-encode equality selects only the signed canonical key text. | Handshake parser/duplicate headers/raw-target handling, real auth nonce commit and atomic session-binding receipt remain separate. |
| WS-R3 | Explicit fixed client/server code sets; server excludes 1010; all legal incoming closes receive normal server 1000. | Reserved 1004, one-byte close, control length126 and high-bit length fail the literal rules. Client1010 remains legal without a server1010 echo; private4000..4999 remain profile-valid. | Encoder/parser/close state must enforce both direction and profile set; real incremental I/O is not proven. |
| WS-R4 | Nonblocking reactor; absolute handshake3000ms, header500ms and complete-control1000ms; separate bounded auth/data lanes; stale/late results cannot authorize. | Deadline sums, nonextension by byte progress/pong and partial-write/revoke ordering match all finite examples. | A pure clock model does not prove actual250ms checks,1s revoke close, lane/OS recovery or real fairness. Actual integration and fault tests remain open. |
| WS-R5 | Whole RFC frame bytes include headers; application queue, encoding buffer and control reserve are accounted separately. | Payload262134+header10 fits262144; payload262135 fails. Application queue524288 plus builder262144 plus two127-byte controls totals786686. | Enforce before allocation/enqueue, preserve active frame until release, bound all encoder intermediate chunks; wire arithmetic is not RSS/TLS/kernel memory proof. |

The registered 3000/3003/3008 whitelist is a versioned local-profile choice,
not a claim that every other 3000-range value is universally malformed RFC.
Future registry/profile changes require review. The direction matrix does not
consult a live network registry at runtime. The existing thirty cases stay
`NOT_RUN_REQUIREMENT`; the twenty-eight additions have the same status.

## Exact arithmetic evidence

[Independent calculator](../evidence/runs/private-stream-v2-independent-review/check_vectors.py)
reads the exact Git blobs, parses the design vectors and computes finite byte,
integer, Base64/SHA1 and model-clock results. It imports no UTA implementation,
production auth or frame codec, and opens no database or socket. It verified
that all five files introduced by c68 have identical bytes at c68, V2 and the
review checkout. The [result file](../evidence/runs/private-stream-v2-independent-review/results.json)
records those original hashes and all five V2 input hashes.

All twenty-eight V2 cases were checked for their arithmetic or conditional
policy expectations. C031's 2,000,008 Python characters encode to 6,000,008 UTF-8
bytes without allocating that large test string. C036 recomputes both accepts.
C037–C042 calculate actual literal header/mask/code fields; C043–C050 check wire
and queue budgets; C051–C056 check fixed model deadlines and refusal to move
one because another byte, stale result or unrelated pong arrives. C057–C058
verify empty/private close and the exact directional set. Expected HTTP codes,
nonce refusal, SQL behavior and real scheduling are requirements, not outcomes
of executing those subsystems.

The reviewer's earlier finite-vector classifier is retained as original review
evidence, including its disclosed instrumentation correction. V2 now explicitly
chooses normal1000 for every legal client close and a narrower registered3xxx
profile; that is the reviewed amendment's contract. The old reference helper
was never a production or general protocol implementation.

## Permitted implementation scope

The integration owner's existing GO can remain restricted to a standard-library
pure codec, canonical handshake arithmetic and bounded encoder/buffer library.
This review does not add a listener, auth checker, database path or public
route to that permission. The library should accept caller-provided bytes and
model time and expose explicit partial-input/partial-output states, with no
financial imports, writer startup or implicit authority creation.

Two concrete regression conditions belong in the next slices:

- A bounded encoder must not assume `JSONEncoder.iterencode()` creates only
  small pieces. One large input string can yield one large encoded chunk.
  Reject/preflight or segment oversized scalar strings before producing a
  chunk beyond the wire cap; check non-ASCII and escaping expansion too.
- The future byte-limited event helper must not hand a shortened prefix to the
  old count-only `_page(limit=32)` and falsely conclude the range ended. For
  `after=400`, `until=450`, two64KiB events407/413 and a next1-byte event420,
  the128KiB page holds only407/413: `has_more=true`, `next_after=413`. It must
  not advance to450 and skip420. With an oversized next event, emit the valid
  prefix if appropriate and then refuse at that event within the original
  catch-up range; no silent range reset or cursor skip is allowed.

The second condition is a future reader regression requirement, not a new SQL
probe or a blocker to the already isolated pure codec work. The code author
was notified of both conditions before an immutable implementation review.

At this review time the separate codec worktree has tests-first commit
`7ff78cee0d70721ee36fba7f9adcf7bffad96450` and a mutable untracked implementation.
This closure deliberately does **not** inspect or approve that mutable code.
A later immutable runtime commit needs its own independent literal, memory,
error and partial-state review. Even a passing pure codec does not establish
persistent nonce uniqueness, key-revocation race handling, same-snapshot H,
backpressure under real sockets, installed package or production WS capacity.

This is a report-only continuation with no deployment or data migration. Its
rollback removes only the added review continuation; keep original findings,
requirements and raw results. Existing M2/long-run sources and their NO_GO
results are unaffected. Production, real funds, HA and real-time deadline
approval remain false.
