# PR47 first CI: RAW evidence accepted; first push failure preserved

Independent RAW review accepts the bounded first-CI evidence in collector seal
`2d0ba927da063bb017a6266eb68e0c117281731d`, tree
`e30c74a36602cb8c4bb20be3eec78c4e113358b6`. **The first push remains FAILURE.**
The separate PR-merge success does not make this an all-green qualification.
Full qualification is null; production, financial activation, capacity and
performance acceptance remain false. This new review closes the collector's
then-PENDING evidence review without rewriting its original17-file seal.

Source C is `05ebc17f5a2a4934a2ee27f14ecdfe0a7067bd45`, tree
`15fb593f0786affb953eeafbbecf3f44adb9dabb`, base
`112e5444d170a4fcdab747c4d23671058a6ec6c5`. Saved provider metadata confirms
actual merge `341779921dea79d4c8d831e5bb79fa5cb5360093`, parents [base,C],
with that same tree. The two commits and their qualifications stay distinct.

| First attempt | Matrix/result | Evidence actually checked |
| --- | --- | --- |
| push44279325039 | Py3.10 job134715524250: FAILURE | Original2061 tests,0F/1E/0skip; worker exit1 |
| PR44279599639 | Py3.13 job134716479374: SUCCESS | Original2061 tests,0F/0E/0skip; worker exit0 |
| Remaining six successful jobs | SUCCESS | Saved metadata only; no invented unit counts |

Both runs are attempt1 and were already terminal at the collector's first read.
The two saved run records, eight jobs/steps and twelve original connector
observation receipts match the SAFE projections. There is no subsequent terminal
polling record. Download/request-once and no-rerun claims are consistent with the
sealed ledger and administrative history; this reviewer made no network request.

Both sampled worker objects have exactly the baseline seven fields: six typed
integer counters and a boolean unittest_passed. The optional lease-observation
pair is absent from worker and summary. A different nine-field contract was not
substituted, and no full qualification was invoked. Each unit's372 before/after
source hashes is unchanged and matches exact C Git bytes. The successful unit
records the actual merge commit, whose equal tree supplies its C byte binding.

The unique push ERROR is
`test_durable_process.DurableProcessTests.test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers`.
Its exact source-bound stack is test424 -> publish_market1532 -> flock263 ->
sharding267 ServiceError, following BlockingIOError errno11. The source literal
is router_busy/status503; the exception instance's code attribute was not
observed. It fails at the first timeout4 EX admission after the capture polling,
STOP request and rollback calls returned, before publication body/receipts and
the next elapsed<5 assertion. Neither actual lock owner nor kernel stop state
is proved. The PR3.13 original records this same test as ok; that does not erase
the push ERROR or establish a common cause. Cause remains **UNDETERMINED**.
The separate CODE investigation `8000f6fc8182f7b6ff967ac25364b63ee051731e`
contains conditional hypotheses, not newly observed causes or a reproduction.

Three original ZIPs total250,487 bytes. Each matches saved provider length and
SHA256, and all25 member CRCs/lengths/SHA checks pass: two unit archives with
three members each and one nineteen-member report-only package archive. The
two units' separately saved summary/worker/log bytes equal their ZIP members.
The decoded failed job log is timestamp-prefixed pretty JSON, not the unittest
trace/footer: its one printed summary exactly equals the original unit summary
with the two source maps omitted. The first administrative parser assumptions
were corrected against those unchanged originals. No wire-byte claim is made
for the connector-decoded UTF-8 log, and no complete log/profile is exported.

The selected successful package belongs to the PR3.13 merge qualification.
Its report records seven checks true, no missing/mismatched entries, eight
installed tests and eight commands with return0. The private textual test report
also has eight distinct ok IDs and its matching footer. Twenty-five module
origins are within the reported installed site; isolation, unset PYTHONPATH and
helper hashes agree. The62 runtime hashes, including static HTML, match C and
the recomputed canonical runtime-map digest matches both reports.

The7051 reported required paths include all108 Git delta paths and the169-path
necessary closure. This is report-backed archive/installed evidence, not an
independent unpack/recompute of wheel/sdist binary payloads. No large container,
wheel or sdist was downloaded by the collector or reviewer, and this does not
supply full financial qualification.

All476 declared regular non-symlink physical source files equal their C Git
blob bytes/modes/hashes. The108 path/status delta equals base-to-C Git diff.
UTA61 Python files, tests, tools, config, workflow and build domains are unchanged
from base. Inclusion of new benchmark source bytes in a source map does not
prove those observer methods executed in ordinary test discovery.

Profile provenance is explicitly split. The active full plan is SHA256
`03c789c6cc191c4a86af1bcf306b46830c6ca8cbf1b3394673168833c034f21c`.
Its host/aggregate controls, two manifest hashes, current63 input bytes and
original-scan63 origin bytes match C. Their union is66 sources, equal to the
existing public SAFE report's unchanged66 before/after source receipts. The
planned host argv explicitly selects that full plan and its SHA; it contains no
execute flag and grants no authority. The host reads args.plan; the once driver
reads the exact manifest selected by its approved CLI hash. The four actual
scripts contain no generic plan.json literal.

The historical generic plan still declares an old25,278-byte aggregate while C
contains28,613 bytes, and its two old manifest pins differ from current C. Those
differences and historical values are preserved; they are not mislabeled as a
fully matching current plan or a CI cause. This review checks static provenance
and old public source receipts only. It neither reopens old private six-DB
profile originals nor repeats/requalifies their native/performance results.

The administrative record matches five original stop files, their script hashes
and exit1 records, plus a separate JSONDecodeError probe. The private execution
closure preserves six nonzero administrative calls followed by successful
derivation, with zero target/CI invocations and no repeated API/artifact record.
The first actual format check is exit0 with empty stdout/stderr. The initial47
private receipts remain unchanged within final51; these events are neither CI
reruns nor business test failures.

The17 SAFE files total300,137 bytes and match collection seal SHA256
`55911ab33d5eea92cd509815e271947fc4a622fba31225759ad39824487a7a26`.
The private directory has0700 mode; all51 regular originals are0600 and match
the final opaque length/SHA inventory, totaling2,270,855 bytes. Finite public
PEM/token/signed-URL/credential-header checks, identity-key checks and comparison
against raw UUID/worker-binding strings find no leak. Download references,
connector bodies, original ZIPs, complete job logs and binding/profile payloads
remain private. This review adds only this note and a summary/hash JSON.

No target import/compile, SQL, native/controller/child execution, current or
protected PID/proc/pidfd/signal access, API/download, rerun, source fix or push
was performed. No H48/native PASS, local component result, PR matrix green or
old plan mismatch replaces the first ERROR. Machine-readable checks and the
limited evidence-acceptance conclusion are in
[raw-review.json](../evidence/reviews/pr47-first-ci-independent/raw-review.json).
