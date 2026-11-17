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
