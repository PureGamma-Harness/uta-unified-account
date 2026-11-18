# Adaptive review: retained spawn cleanup and bounded model evidence

This report supplements, without modifying, the original b689/9135 review. It
reads the new b02a4e45ec0132e43d0c94fb7c7ab3490d9edea3 delta and the subsequent
terminal-block refinement ff814d4bcaee079b0e0503ea8072c24e3563c443. No model,
unittest, SQL, native process fault, old job or implementation change was run by
this reviewer. Root remains responsible for any separately bounded actual-driver GO.

## B1–B3 disposition

B1 static primary barrier is closed in b02: start and _spawn reject blocked or
pending cleanup before creating a new child. _spawn_pending_cleanup persists the
old child, stop/gate and unclosed handles. If cleanup stays unknown, close keeps
those references and retains the supervisor FD, rather than silently handing the
layout to another parent. A confirmed later cleanup can resolve the cleanup
barrier; a new registration does not erase an unresolved predecessor merely by
succeeding. This is static control-flow evidence, not a physical kill/join test.

B2 static ownership inventory is closed in b02: each successfully closed handle
is removed individually, and the remaining list/process/gate stays referenced.
_worker/_start_gate/pending entries are removed only after child exit and the
last process.close succeeds. Exceptions retain incomplete state for another
cleanup attempt. The modeled receive-close failure covers this branch. The pure
router uses supervisor_fd=None, so an actual retained/released OS descriptor is
not demonstrated by that model; the conditional FD guard is source-inspected.

B3 static stop race is closed in b02: after acquiring the mutex, the monitor
checks stop again, and the retry condition also checks it. The contended-mutex
model sets stop at entry and verifies no new spawn. This covers the identified
retry-path interleaving, not every preexisting close/monitor-join timeout scenario.

The first adaptive pass found a further mixed-state boundary: b02 could clear a
terminal registration block when an initially failed cleanup later succeeded,
although the same terminal error with immediately complete cleanup stayed
blocked. The author confirmed this was contrary to intended policy. Refinement
ff814d4 stores the original registration-retryable cause separately in pending
state and clears the blocked marker only for that known-retryable cause.
Terminal/unknown registration failure remains blocked after cleanup; a ninth
pure model verifies close recovery followed by rejected start and _spawn. This
closes the additional static policy defect without replaying or rewriting a nonce.

Within these narrow changes no further concrete static blocker is identified.
This permits review of the separately pinned bounded native plan; it is not an
execution authorization, original-CI reproduction, accepted runtime fix or release.

## Model evidence identity and limits

The original eight-case source has test SHA
d6b4f7b73cda0b5c7900642083d2d18c1b6bcc228339329e90510c403f29c602.
Original-proof binds an e439 imported runtime file under a fresh baseline path
with matching runtime SHA. Its raw result is eight tests, six FAIL, one ERROR
and one PASS. The fixed-eight raw reports eight PASS in0.027s. That fixed raw did
not record its actual same-process import path or complete invocation environment;
the author explicitly retains that gap. A separate prepare-only snapshot cannot
retroactively prove which runtime a previous process imported. Neither file is
rewritten or elevated to stronger evidence. These are constructed model errors,
including a modeled append/lost reply, not real SQLite COMMIT or native protocol
error reproduction.

A later direct-file CLI omitted PYTHONPATH and failed at import with
ModuleNotFoundError before the model suite. That first invocation failure and its
corrected-command nine-PASS result remain separate. This is an invocation error,
not an extra native product failure. It is not used to relabel the original CI.

Author evidence26bd4d3cde0bd71e9b7cbf1be0e4c5ec81ea7e1e adds a small same-process
model probe. Its first raw stream records PID411860, actual imported own-tree
runtime path, all62 runtime SHA pins to ff814d4, test SHA
c0024c905b077a310178cb7d38fffa5a85ae3fe5e28bb9d361e7c21524801080, native-driver
hash and model-probe hash before executing the model suite. The same PID then
reports nine PASS, zero FAIL/ERROR, native_executed=false; unittest duration0.026s
is not presented as measured whole-process duration.

This reviewer checked every reported runtime hash against the immutable ff Git
blob, matched the tests/probe/driver to their committed bytes, and inspected the
loader plus hard mocks for sqlite.connect, BaseProcess.start and os.kill. The
probe loads only SpawnRegistrationUnitTests. Fake contexts/processes/connections
and simulated time/registry outcomes intentionally exercise control flow; they
cannot prove kernel PID exit, real lock release, an actual SQLite COMMIT, money
conservation, the remote CI cause or native throughput. A same-process pre-test
source pin is recorded; no post-test full-source rehash is claimed.

## Compatibility and unchanged boundaries

HTTP managed diagnostics now projects supervisor_alive and the fixed typed
last_spawn_failure fields. An explicitly false supervisor suppresses public
ready/financial_ready; malformed boolean/count/error shapes raise a fixed
503 diagnostic_unavailable rather than expose raw messages or nonce. Unknown
extra fields are filtered. Legacy reports missing supervisor_alive retain the
previous compatibility fallback and expose None, rather than gaining a new
claim of supervisor health.

Unknown after-COMMIT registration remains UNKNOWN, its possible immutable row is
not deleted or rewritten, and a new attempt uses a new PID/nonce after permitted
cleanup. Registration recovered=true remains narrower than actual child READY.
The existing worker/gate-before-financial-authority ordering, storage FULL/busy
settings, original0.6s fixture lease and original4s API testcase are unchanged.
Retries remain bounded in interval/rate, not a finite lifetime attempt budget;
synchronous registration/cleanup still holds the parent mutex. This review does
not promote that to a measured cross-shard fairness or recovery-latency guarantee.

The original PR22 1801/0FAIL/1ERROR and its associated supervisor WAL protocol
trace remain exactly as preserved in b06d0b5/349223b. A model red/green mechanism
and static improvement are not proof of their unique historical cause. Source,
actual-child lifecycle/receipts, final cleanup and full exact-source matrix gates
still require their own reviewed evidence. Overall production remains NO_GO.

The new sparse evidence contains only immutable deltas, original model raw copies,
source/hash checks and this report. No original review/raw artifact is altered.
Rollback of this review is to omit the evidence-only commit while retaining all
original results; no production deployment or runtime rollback was performed.
