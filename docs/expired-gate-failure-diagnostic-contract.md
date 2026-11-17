# Failure-only evidence for the original expired-gate case

Base: 5a2961134aedaef9914d4cdd0247bb8795fb9b90. Purpose: if the original case
fails again in a full CI matrix, retain immediate cause clues before its existing
cleanup. This does not fix runtime liveness, change the original lease/capture/
recovery/API5 or lifecycle15 budgets, resolve the old CI failure, qualify source91
or grant production approval. All original one-case and ABBA16 raw evidence stays
unchanged.

The sole integration is an exact `if primary_error is not None` block in the
existing original testcase's finally, immediately after its existing primary
exception capture and before its original cleanup. The helper is imported lazily
inside that branch. A successful original case adds no diagnostic import, log,
clock/thread collection, source read, wait or financial call. The new pure test
strips only that exact branch and compares a canonical whole-module AST hash to
the original base. This covers all original assertions, financial calls, timing
parameters and cleanup order. Empty type_params is normalized across Python3.10+
AST versions; line attributes are irrelevant. No financial testcase is imported
or executed by the pure tests.

`tests/expired_gate_failure_evidence.py` reads only already-held observation dictionaries,
original primary/publisher exception objects, the three relevant Python code
stacks, monitor-thread alive state and in-memory stop Event, plus monotonic,
CLOCK_BOOTTIME and UTC clocks. It makes no SQL/status call, source read, /proc
operation, process signal, sampling thread, thread start, join, sleep or wait.
`sys._current_frames` is consumed only for main/monitor/publisher roles. No frame
locals or source lines are read. This is a nonauthoritative before-cleanup
snapshot; it cannot describe cleanup actions that have not occurred yet.

The explicit observation schema includes numeric original horizons/milestones,
PID/birth/UID and native lease owner/generation/expiry/now/active fields. It retains
the final eight existing lease-read records, counters for existing captures/undos/
cleanup errors, and the final capture's numeric timing, candidate/retained counts
and native writer-probe available/errorcode. No new native state is queried.
Omitted state is unknown, never healthy, an authorization, renewal or a grant.

Privacy rules are structural. No exception message, args/notes, raw pathname,
source line, arbitrary class/function name, owner nonce, payload, market hash,
private CID or unlisted dictionary key/value is serialized. Exception types and
string codes use fixed enumerations; native SQLite errorcodes may be bounded
integers. Code locations are fixed module labels, listed function names (otherwise
<unlisted>) and line numbers. Unknown/malformed values are omitted or null with
drop counts. The original exception object and observation are not modified.

The entire ASCII JSON line, fixed prefix and final newline are at most32KiB.
Collection limits are eight publisher exceptions, two chain links, twelve frames
per exception and twenty frames per relevant thread. Further limits are explicit
in drop_counts. Frame/chain counts ending in `_at_least` are conservative lower
bounds without an unbounded traversal. Unknown fields are counted only at visited
projected dictionaries; nested collections summarized by counts are not traversed.
If the byte cap is reached, the helper drops bounded sections and records payload
trimming. Any collection/serialization failure falls back to a bounded literal
collector_failed record. A single best-effort stderr write returns False on an
exception or partial write; it never rethrows or retries. The surrounding branch
also catches diagnostic import/execution exceptions, so ordinary logger failures
cannot replace the primary failure or skip existing cleanup. This is bounded
output, not a hard real-time guarantee for a stalled operating-system log sink.

The permitted first validation is one CPU4 pure-test invocation with a3-second
outer bound. It exercises original-AST preservation, the actual success hook,
secret-negative exception/observation/path/locals vectors, byte/item/frame limits,
input immutability, writer/collector failure and forbidden operation inspection.
All raw outcomes, including a failure, must be retained. No extra original native
case is authorized; the new source is exercised only in the later separately
approved complete matrix. Another group and root must review this test-only
patch before a new stable freeze.

No production module, configuration, schema or financial rule changes. Deployment
is a future reviewed test-source freeze; rollback is removal of the one diagnostic
branch and its test-only helper/tests, preserving raw evidence. Historical CI
failure and overall production NO_GO remain unchanged.

The first author preparation incorrectly collided with existing tests/test_failure_diagnostics.py. Its unexecuted overwrite/diff and provenance are retained under evidence/reviews/expired-gate-failure-5a/preparation-error. The bad local commit9ba is excluded from this corrected candidate ancestry; every existing test other than the one explicitly amended finally is byte-for-byte preserved.


## First authorized pure validation

Exact corrected candidate315a71d0bf67c872a048570038bdf328fb821544 ran the new
unique suite once on CPU4 with Python3.13.5 at2026-11-17T15:54:24 UTC.
All11 tests passed in0.116s; whole process duration was0.266144726s, within its
3-second bound, without watchdog or changed source. Raw BEGIN/END/unittest and
SHA manifest are under evidence/reviews/expired-gate-failure-5a/pure-once-315a.
No SQL, service, original native testcase, or follow-up success rerun was used.
This is test-helper verification only; another group/root review and a later full
matrix remain required before a new freeze. It does not resolve runtime liveness.

Drop counts describe explicit projection and collection/byte caps, not a global
count of all possible redactions. Unknown code/type labels remain explicitly
<unlisted>; unknown nested data summarized only by counters is never traversed.
The author preparation collision was found before any test execution. The bad
local9ba commit remains available solely for provenance and is not an ancestor of
this corrected candidate. All172 existing test files are inventoried:171 are
byte-identical to5a; the only existing-file difference is the exact six-line
failure hook in test_durable_faults.py. Existing test_failure_diagnostics.py is
restored byte-for-byte; the added suite has a new unique name.
