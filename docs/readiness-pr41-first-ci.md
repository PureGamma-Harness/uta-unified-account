# PR41 first CI: both matrices remain RED

Exact head C is `cdfa1844fe7ae515b5d69b495a0593d337223e77`.
PR41 remains Draft, based on PR34 at e01fde9. Its merge commit is
`72a2fabe12e2adcd9c0c37928b7181eb7b587250`. The remote head and merge
trees both equal b8ae5b8a37fafe37e8b48f1bbdb857a0d7dcb24d; their CI
qualifications are recorded independently.

| Event / attempt1 | Run | Checkout in failed job | Py3.10 | Py3.11 | Py3.12 | Py3.13 |
|---|---|---|---|---|---|---|
| Exact-C push |44245414846|C|success|unit failure|success|success|
| PR41 merge |44245591070|72a2fabe|success|unit failure|success|success|

These are one push run and one PR run. Root reported that an earlier short
detached-HEAD refspec push failed without a remote change; that is not an
additional CI run. Both matrices are terminal failure. No rerun, dispatch or
new push occurred during this collection, and polling stopped at terminal.

Each failing Python3.11 job ran1842 tests with1 failure,0 errors and0 skipped.
The actual runtime was Python3.11.18/GCC15.2.0 with SQLite3.46.1. Push unit time
was388.104s (wrapper389.684632222s); PR merge unit time was379.916s
(wrapper381.355220387s). These timings are observations, not performance gates.

Both complete failed-job unittest logs explicitly record each of the seven new
BeforeQuoteReferenceTests methods as one `ok`. They also each record
`test_malformed_missing_and_oversize_persistent_quotes_fail_closed` and
`test_same_version_changed_persistent_content_is_not_reused` as one `ok`.
Successful unit artifacts were not downloaded; other jobs' unit success is
known from provider step metadata, not newly collected individual method logs.

The sole failing method in each run is
`test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`.
Keep the observed checkpoints separate:

| Event | Original assertion | Available same-test evidence |
|---|---|---|
| Push |test_durable_faults.py:1525: original bound PID did not exit within the unchanged five-second recovery horizon|One original UTA_EXPIRED_GATE_FAILURE_DIAGNOSTIC JSON with captured thread, monitor/publisher, lease and timing observations.|
| PR merge |test_durable_faults.py:1456: bound child did not leave SH after undo within original capture horizon|One original marker JSON with capture/probe/undo and associated thread/lease/timing observations.|

The original marker JSON occurs before the FAIL tail. An initial tail-only
review missed it; the complete original logs were always retained, and exact
marker projections now preserve the available payload. Frame/lease/time samples
do not establish operation duration or a common HOL cause. No local replay or
PID/probe was performed. These new failures are not substituted for either
original PR34 failure, whose cause remains open despite the two current methods
passing in these particular failed jobs.

Both captured356-file source maps are unchanged before/after and match exact-C
Git bytes. PR merge's actual checkout SHA remains distinct, while its tree is
identical. Of the old local native69 closure,65 files are in the CI source
capture; the four lab harness files are Git-only auxiliary inputs and were not
imported/executed by this unit proof. Historical capsule maps are source identity
aids, not executions or transferable authority. Positive source flags here are
actual new CI fields; no old PENDING, null, failed record or source pin is changed.

Exactly two failed unit ZIPs were acquired:14401902025/95438B and
14401269000/95098B. Their provider digests match original bytes; each has3 valid
CRC members (summary, worker-result, unittest). Both complete decoded job logs
are preserved. Container and decoded text scans for the five declared
credential/private-key/signed-URL classes are clear, with empty ZIP comments.
HTTP headers, signed file-service/transfer references and raw transport errors
remain in a private directory outside Git.

Exactly one successful exact-C push small package artifact was acquired:
14402101902,55641B, SHA256
cca2dcbd99476f912e32a81742a43b4e8234bad82e07e4b7cc5bb0232b04b89e.
Its19 CRC members and bounded scans pass. The original report has all7 archive
checks true and no sdist missing/mismatched files. All6433 tracked paths match
the exact-C required-file set; all126 new/modified paths and the precise guard
SHA256SUMS path are selected. The62 runtime-file hashes match Git and the
reported runtime-tree digest. The installed report for Python3.10.22/SQLite3.46.1
has8 tests,0 failures/errors/skips,8 commands returning0, isolation true and
PYTHONPATH null. Large wheel/sdist bytes, successful unit ZIPs and PR-merge
success package reports were not fetched. This is a report-bound qualification
for that one successful push job, not local installation or production approval.

Collection incidents are retained separately from CI outcomes: a first V8
scanner preparation error (TextEncoder absent), the first package parser's
flat-name assumption, and a large-JSON tool-output truncation error. Original
parser source/first package traceback and unchanged archives are preserved.
Only the workflow-declared installed-validation prefix was added to the parser;
the same original ZIP then decoded successfully. No CI attempt was repeated or
washed green. Direct gh redirect reads returned Forbidden/zero bytes; the
official connector and its file-service route supplied the valid originals.

The scoped payload totals246177 ZIP bytes,52465 decoded job-log bytes and
1485192 expanded archive bytes, below each individual and64MiB total cap.
All evidence is directed public synthetic CI output checked before export.
This group ran only bounded offline standard-library inspection, Git/file reads
and authorized GitHub reads: no target tests/builds, SQL, native/metadata probe,
PID/signal operation, dispatch, push or service mutation. Old local pure/native
and metadata results retain their separate scopes; production_approved stays false.

Evidence lives under evidence/reviews/readiness-pr41-first-ci/. The exact
source/run binding, terminal matrix, raw artifact integrity, selected method
outcomes, phase projections, parser incidents, package selection and source maps
are separate JSON records. Original ZIP and text bytes are not reformatted.
