# Independent review of failure-only expired-gate evidence

The first reviewed safe candidate is
`b58e587bf8eb17c1c8449e65c7368a8fc2ec4a31`, following corrected315a71d,
from baseline `5a2961134aedaef9914d4cdd0247bb8795fb9b90`. Independent Git
inspection confirms the bad preparation commit9ba043d is not an ancestor. Its
collision provenance remains preserved. All172 prior test files are inventoried:
171 match baseline bytes; only the original expired-gate testcase's finally has
the exact six-line failure-only lazy hook. The existing test_failure_diagnostics.py
is byte restored. Removing only that exact hook yields the baseline whole-module
AST, independently compared directly with baseline Git source rather than trusting
the author's saved hash. Production runtime bytes are unchanged.

One separately authorized independent Python3.10.22/CPU3 invocation ran only the
new unique pure suite at15:59:46 UTC. All11 tests passed without failures, errors
or skips, in0.141 unittest seconds and0.317607916 process seconds, under the3-second
bound. Four relevant file hashes and tracked cleanliness remained unchanged. Raw
BEGIN/END/unittest and hashes are retained under the independent evidence directory.
No financial testcase, SQL, native reproduction, process signal or service ran.
The first author11-test Python3.13 result and its raw remain separate evidence.

The reviewed helper projects explicit numeric/boolean fields, exception type/code
enumerations and fixed file/function labels. Exception messages, args/notes,
frame locals, raw filenames, nonce and arbitrary dictionary values are excluded.
Only three existing thread-role stacks and in-memory status are observed; no new
SQL/status/proc/source introspection, signal, thread start or wait is added. The
whole ASCII record is capped at32KiB with explicit truncation/drop indicators.
Single-write/collector errors do not replace the primary failure, and original
cleanup follows unchanged. The byte cap is not a real-time bound on a stalled
stderr sink, as the original contract already states. The success path performs
only the new false condition, with no lazy diagnostic import or collection.

This first proof applies to exact b58 bytes and11 tests only. A subsequent scalar-
privacy tightening inafe275e is separately reviewed and tested; its new twelfth
case is not backfilled into this original result. Diagnostic evidence can aid a
future original failure without fixing runtime liveness. Source91's old CI failure,
its unknown cause and all incomplete/NO_REPRO historical observations stay unchanged.

## Final safe scalar boundary afe275e

Final safe source is `afe275e95d832e238e033faa84b3ee5cae1b8431`, with helper
SHA872b38c73c10faa360ddebfb85328b23b847b08311174c0abcbcf95700f53e56
and unique suite SHA12d3c2bb29a3c86d26a36cd5e9ae01f7305025d9a5156f54809319d1d9022e1a.
Its additional patch also validates stdlib Thread/Event/clock returned scalars:
nonliteral booleans and nonbounded/noninteger clocks become null with drop counts,
so a malformed stdlib return cannot bypass the same privacy projection. It adds
one explicit synthetic-secret negative vector; the old11-case proof is untouched.

One newly authorized Python3.10/CPU3 invocation ran these final12 pure cases at
16:02:42 UTC, all passed without errors/failures/skips. Actual process duration
was0.214462748 seconds, unittest0.128 seconds, below3 seconds with no timeout.
The exact final author HEAD, four relevant file hashes and tracked cleanliness
were verified before/after; no original native case or SQL ran. All three raw
records and an exact hash manifest are separately retained under python310-afe-once.

The independent source-contract checker was reapplied to finalafe Git blobs with
only its candidate constant changed. All172 prior test files, whole original
module AST, corrected ancestry, production-runtime identity and the six-line hook
conditions still hold. Neither the bad9ba preparation commit nor a replacement of
its old test file is part of this safe chain. A success still imports/collects
nothing; on failure, collection remains a nonauthoritative before-cleanup snapshot,
with bounded output and a single best-effort write preserving the primary error.

**No concrete blocker remains to integrating safe315a71d→b58e587→afe275e as a
diagnostic-only test change.** Integrate this safe chain and these independent
proofs; exclude bad9ba. A fresh exact candidate still needs its complete local QA,
CI, package and separately planned short/long synthetic observation gates. The
patch does not repair or prove five-second runtime recovery, clear source91's
original failure, authorize customer traffic, or sign production/real funds.
Stopping this optional test collection or reverting its exact hook/helper in a
new commit is rollback; preserve all original raw and failure history.
