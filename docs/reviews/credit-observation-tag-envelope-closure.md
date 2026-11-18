# Independent CODE closure of the credit-tag pure envelope

Decision: **COT-CODE-001 and COT-CODE-002 CLOSED in static scope** for source
`834ad6e4da8a97c2246b0a49d82085183f73519c`, tree
`691c4d0a6d7a7238705b4af745aaac490756f6ed`. This supplements independent review
`cb875878649ab4c4ba013e34ebac734c87810cac`; its original finding text is
preserved. No target execution, test result or execution GO is granted.

The candidate worktree was read only. This review used Git/text reads, file
metadata and an independent JSON/hash/Git data reader. It did not compile or
import target source, calculate an artifact, execute tests, open SQLite, start
a worker/thread, inspect a PID or perform a signal/network/native probe.

The original runtime Enum change, artifact implementation, all serializer and
validator guards, live-global exclusions and validation source have no diff
from reviewed 7030. The old 7030 plan is retained byte for byte under
`once-plan-7030d121-NOT_RUN.json`, with its original SHA
`2e9c9a91d56435949158131d740a6680c74e0f946fd41f73a1d2a9dc13afb6cd`.
It remains a zero-attempt NOT_RUN preparation, not RED.

The new plan is 14993 bytes with SHA
`8f12dd7a2ad9faabf4981499dee4bf011111273a48bf797678053dbc684ee726`.
All 65 enumerated physical inputs independently match their plan lengths/SHA
and exact 834 Git blobs, totaling 1342330 bytes. The current UTA Python
inventory equals the 61 retained UTA paths. The other four inputs are the
focused test, inner driver, outer driver and unchanged validation source.

`COT-CODE-001` is closed by an exact complete-map assertion in the existing
full-artifact method. The inner injects a 61-entry expected source map derived
from the verified retained plan, separately from the production artifact's
physical source enumeration. The actual returned `source_files` must equal
that full map. Explicit extra/missing map controls also compare against it.
The real artifact and validator remain unchanged, and physical artifact source
reads do not become import/compilation inputs. Loaded UTA code and selected
validation predicates continue to come only from retained buffers.

`COT-CODE-002` is closed by the fixed outer entry and mandatory parent-captured
inner mode. The inner now requires the injected capsule and
`--parent-captured-stdio`; its previous dup2/raw-file redirection is removed.
The outer starts one owned timeout/taskset interpreter with both OS stdout and
stderr piped to its selector. Bootstrap, taskset, timeout, Python and native
FD1/FD2 bytes therefore reach the same enforcing parent collector. The inner's
Python stream quota is an additional check, not the FD-level enforcement.

The parent withholds 512 of 262144 bytes for its single trailer. It charges a
payload request before its one FD write. Overflow, exception or short/invalid
write sets sticky failure; reserved bytes are not refunded and no later payload
is written. The parent continues draining its own child streams. The trailer
uses only its independent reservation. Post-size/hash reads are verification,
not the mechanism enforcing the quota. Raw failure prevents PASS and yields
UNKNOWN/125 even if the inner reports success.

The outer checks actual HEAD, physical/Git source bytes and approved plan SHA
before constructing a new exclusive capsule/output namespace. The plan pins
both drivers but does not include its own hash as an input, so there is no
self-referential checksum loop: root supplies the plan SHA separately. The
bootstrap validates capsule SHA, retained plan and every input pin before
compiling the retained inner source. The retained-buffer UTA loader and test
globals cover all six selected methods. No missing-extension-path assumption
is introduced for the host's built-in SQLite module.

The hard host limit is `/usr/bin/timeout --signal=KILL 20s` followed by taskset
CPU 1 and the declared absolute Python with `-I -S -B`. Parent preparation binds
CPU 1 before its Git children. Only its own new timeout process is waited for;
no earlier process is adopted, inspected or signalled. Target exceptions and
bootstrap/timeout errors retain their first pipe output and actual exit facts.
Incomplete END, EOF, reap, source checks or raw capture cannot qualify PASS.

The 22-second parent interval is a **completion/classification deadline**, not
an additional OS hard-kill timer around parent filesystem reads/fsync. The code
checks the deadline around post-state and final publication, emits TAIL and
returns UNKNOWN/126 when late. Root's caller must independently observe actual
outer exit/reap and TAIL; an earlier END cannot certify that future event.
Blocking IO has not been tested or given a hard parent termination guarantee.
Initial Git/source preparation is outside this target/drain interval and must
be reported separately. These boundaries qualify the source's deadline claims
without weakening the twenty-second host timer or the PASS gate.

The plan's case-group counts sum to 22 and it selects six methods. One legacy
sentence in its limitations still says twenty; this is a non-executable prose
inconsistency. No actual method/subcase observation is claimed by this review.
The future evidence must distinguish six method outcomes from the bounded
source-case count. No new selected method or target capability was added.

This closes the two prior code requirements for root to consider one exact
focused run. The original CI's missing attribute remains UNKNOWN and every
first failed outcome remains failed. A focused PASS would not prove whole CI,
native recovery, financial activation, capacity or production readiness. There
is no data migration, rollout or retry approval. Rollback preserves all evidence
and leaves the new test envelope unused; reverting to the unsupported old object
tag is not an accepted service rollback image.
