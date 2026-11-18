# PR22 first CI error: independent evidence acceptance

The original CI unit gate is **NO_GO**. This independent read-only review accepts
the archived evidence's integrity, not the product, recovery behavior or release.
No test, SQL connection, service, process-fault experiment, old-job action, timeout
change or CI rerun was performed.

GitHub provider metadata identifies pull_request run44162304965, **attempt1**, on
PR22 head e4396b4b1fd9c2e3a138e48a045feffe158705cc and base
909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0. The actual provider merge/CI checkout is
289ca5d05585ba5fd981a6e11ac2cf8b98d6672e. The failed job134319073058 is test(3.11).
Its original summary records Python3.11.18/GCC15.2.0, SQLite3.46.1 and
Linux7.0.0-1019-azure/glibc2.43; 1801 tests, zero failures, one error, zero skips.
Validation wrapper duration is402.006960575s; the original unittest footer is
400.673s. These are separate clocks, not an inferred per-case recovery duration.

This run has **four jobs**, not eight failed jobs:

| Matrix label | Provider job ID | Whole-job conclusion |
| --- | ---: | --- |
| 3.10 | 134319073520 | success |
| 3.11 | 134319073058 | failure |
| 3.12 | 134319073451 | success |
| 3.13 | 134319073353 | success |

For3.11, Run unit tests failed; complete unit evidence preservation succeeded.
Compile source, demo/replay/acceptance/formal steps and package build/archive/
installed validation steps7–20 were skipped, as was wheel retention step22.
Always-run package-evidence preservation step21 reports success, but the provider
job log also reports no files found/no artifact uploaded. No3.11 package or wheel
artifact is present in the ten-artifact provider index. A successful preservation
step must not be reported as a successful package build. The other three jobs'
whole-job/step success is provider metadata evidence; their package binaries and
unit archives were not independently downloaded or revalidated here.

## Exact original error and associated thread exception

The failed test is
`test_durable_process.DurableProcessTests.test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers`.
At tests/test_durable_process.py:424 it calls
`publish_market(self.market(2), timeout=4)`. The original traceback enters
uta/durable_process.py:1395 at the first EX control gate, observes nonblocking
flock EAGAIN in uta/sharding.py:263 and raises router_busy/503 at line267. This
is an ERROR, not an assertion failure, and does not prove which process retained
the gate or whether a particular old PID exited. No actual per-case duration or
selected-PID/generation witness is recorded in that traceback.

The same original unittest log, immediately following that test's ERROR marker,
contains an uncaught uta-process-supervisor exception:
_supervise:1227 → _spawn:1095 → _record_process:393 →
storage._role_transaction_body:202 → _connect:147 →
`PRAGMA journal_mode = WAL` → `sqlite3.OperationalError: locking protocol`.
Both traces are retained. The transcript lacks per-thread native-clock/PID anchors
for that exception, so textual adjacency does not establish whether it preceded
the timeout, occurred during cleanup/respawn, or uniquely caused the failure.
The background-thread exception does not change the original unittest count from
one ERROR to two. Other intentional fault traces elsewhere in the log are not
counted as additional unittest failures.

The distinct sibling
`test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`
is recorded PASS in this same run. It is not the failed testcase. Historical
single-case/ABBA16 non-reproductions of that sibling cannot resolve this new
failure. Connection_lifecycle received the exact original locations and is
separately preparing a bounded causal investigation; no SQL/native GO is implied.

## Original archive, source bindings and limits

Provider artifact14365340388, uta-unit-validation-python-3.11, has92276 bytes and
SHA-256 9ea4bae56cd6c2697cd613972bbcbf56c0fc3bffbd3c720313fc740ca66eaffc.
The original plugin ZIP matches both provider fields. All three member CRCs pass:
summary.json(75943B), worker-result.json(155B), unittest.txt(361234B).
The standalone summary/worker files match their ZIP members byte-for-byte, and
the original unittest SHA8510a40145092742b23a75b66ba545e83f01ea4b461f26b51444b180cc8821b9
matches the summary. The full original unittest remains inside the original ZIP;
it is not duplicated uncompressed in this small sparse evidence branch.
The two original error excerpts identify their exact original line ranges.

The initial coordinator-reported gh-api download attempt left a separate0B file.
Its original empty residual is preserved under an explicitly distinct name; it
was not replaced by or relabeled as the successful plugin ZIP. No initial HTTP
status, exit code or transport root cause is invented from an empty file.

Every one of the348 before/after source SHA-256 entries is unchanged and matches
the corresponding local Git blob bytes and modes at **both909 and e439**.
An additional complete comparison of320 tracked core paths—uta62, tests226,
formal14, tools17 and workflow1—finds identical paths, blob IDs and modes between
those two commits. This does not claim their entire6127-file trees are identical:
PR22 adds benchmark qualification plan/profile JSONs and evidence outside this
core boundary. Those data changes are not relabeled as changed runtime/test code.

The remote provider merge exists and its message identifies the expected head
and base. Provider checkout-log anchors and the summary identify289 as the
actual CI checkout. That merge object was **not present in the local Git object
store** during this review. The proof here is provider metadata plus348 recorded
inputs and local909/e439 blobs; it is not a local checkout, replay, full-tree
merge verification or reproduction of the remote CI execution.

The source branch/frozen runtime was not modified. This new branch uses a sparse
checkout; no6127-file checkout, private database, private-key/TLS file or large
wheel download was made. The three available wheel archives exceed137MB combined
and were deliberately not downloaded. Provider metadata is a safe projection;
no signed/redirect download URL, credential or raw provider download URI is
printed or committed.

`evidence/reviews/pr22-first-ci311/` contains the original small ZIP, standalone
metadata, explicit0B residual, error excerpts/line index, safe provider records,
21-check read-only integrity result and per-input348-blob index. Re-evaluate with
`python3 evidence/reviews/pr22-first-ci311/audit_original.py REPOSITORY_PATH`.
The script reads archive bytes, metadata and local Git objects only; its positive
integrity result is explicitly separate from the original CI_NO_GO.

No production code, schema or financial rule changes. Rollback is exclusion of
this evidence-only branch from delivery while preserving original raw artifacts.
An independently reviewed fix and new exact-source acceptance are still required;
no production approval or timeout increase follows from this evidence review.
