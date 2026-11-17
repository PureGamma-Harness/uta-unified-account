# Runner R1–R4 author fixes; execution remains NO_GO

The independent review at OWN32c94f2 established real defects in unused runner
35e. Those original red records remain unchanged in
`/workspace/uta-managed-variant-runner-review`; this candidate is a separate
tree based on35e. It does not modify the frozen stability source, financial
runtime, original raw data or live jobs. R5 package-negative binding remains
open for a separate change, and independent closure is still required.

- **R1:** a private pipe carries the launcher's PID and actual CPU set only
  after its real `sched_setaffinity` call. The parent waits within the existing
  wall budget, then compares the actual kernel affinity. It no longer samples
  before the launcher can run. This ACK proves CPU initialization only, not a
  financial READY state. New-session/birth/pidfd cleanup remains unchanged.
- **R2:** any independently derived late financial success makes the result
  red. The supplied deadline flag must also agree with the derived zero/nonzero
  count. A consistently rehashed but contradictory green summary cannot pass.
- **R3:** summary, arrival window, compressed arrivals and actual footer must
  all be in the manifest. Each consumed original is read once, checked against
  its recorded byte count/hash, and parsed from those exact verified bytes.
  Rechecking a different pathname read cannot validate an earlier payload.
- **R4:** decompression uses bounded binary `readline` calls before decoding
  or JSON parsing: at most200 rows and one bounded EOF/excess probe, at most
  64KiB per row and8MiB total decompressed input. The 201st row is rejected
  before parsing/appending. Compressed input is bounded at64MiB. The failed-case
  forensic reader shares those bounds; partial-tail counts stay unqualified.

Author controls in
[`evidence/runs/managed-variant-runner-r1-r4-closure`](../evidence/runs/managed-variant-runner-r1-r4-closure)
passed: Python3.12 has22 pure/dummy cases in0.844s;
Python3.10/3.13 each have18 pure cases in0.135/0.121s. ResourceWarning is an
error and forced GC runs. The real print-only dummy had parent kernel CPUs
`[3,4]`, requested/observed child`[3]`, a real ACK and unchanged parent birth.
No affinity return value was mocked. Only the new private session is cleaned.

The original four independent data vectors were copied byte-for-byte and
author-reexecuted against this candidate:4 PASS/exit0 in0.035s. Their original
35e run remains1 PASS/2 FAIL/1 ERROR. This new author rerun is **not** the
independent verifier's closure or full-suite qualification. Additional binary
spies assert exactly201 reads, bounded per-read sizes, oversized-line refusal,
and aggregate decoded-byte refusal. No gzip bomb or memory-pressure workload
was constructed.

No actual benchmark, SQL, service, eight-arrival replay, profile or long job
was run for these fixes. Deploy only as an isolated review candidate. Keep GO
false until R5, independent closure and a new exact-source qualification pass.
Rollback may restore35e in a separate diagnostic checkout; preserve both old
red and new control evidence. It does not change any financial authority or
allow the older unsafe runner to execute production diagnostics.
