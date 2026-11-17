# Independent review of the original 91e recovery-window failure

The original push run `44104161669`, Python3.13 job `134111871255`, artifact
`14337038689`, executed 1,512 tests and retained one failure with zero errors
or skips. Its bound stopped PID did not produce a pidfd exit observation in
`test_durable_faults.py:1525` within the unchanged five-second recovery horizon.
This is **NO_GO**. The other seven complete CI jobs passed; they do not override
this failure. This review performs only source/AST and original-byte inspection,
with no SQL, process injection, test rerun or gate change.

The fixed implementation under review is
`91e4ae40b5e9b884c54026406299df5000c9c100`. The exact original raw members are
retained by evidence commit `07b0381eef9d6b9a03d0b62b6b7bd1ec1fc81178`.
Their byte hashes and actual result counts are retained in this review's
`original-failure-reference.json`. The review's pure source inspector compares
four current files with their exact source Git blobs and records eight narrow
AST facts. Its own passed structural assertions do not establish recovery
liveness or a cause for the original failure.

## What is established by source

The fixture waits until a fresh lease has at most 250ms remaining, then creates
and starts a publication thread. That thread opens another original native
lease observation, asserts that the original PID/generation is still active,
and only then invokes the original `publish_market(..., timeout=5)`. A scheduling
or observation delay can invalidate that short entry window. Any thread error
is appended to the local `errors` list and sets `done`. The parent immediately
waits for old-PID exit and asserts that result before checking `errors`.
Consequently a publication-thread entry error can be hidden behind the parent
exit-window failure. The original failed log does not dump the fixture's
`publication_thread_entry_lease`, `publication_called_api_at`, `errors`, or
supervisor stack, so it cannot identify that path.

**A publication entry failure alone does not explain an old PID remaining alive
for five seconds.** The production `_supervise` thread independently visits
workers after `Event.wait(.05)`. For a living worker it obtains a native lease;
when the observed lease names that PID and is inactive, it kills that owned,
unreaped child and joins it. This decision does not depend on publication being
invoked. A complete cause for this failure therefore must also explain why
supervision did not observe/act on the expiring selected binding in time, or why
the pidfd exit observation was unavailable.

The single supervisor holds its `_mutex` while visiting all workers. Its
`pipe.poll()` and subsequent `pipe.recv()` are separate calls; readiness of some
pipe bytes is not a whole-frame deadline guarantee. Lease-read exceptions are
caught and converted to `None`, preserving fail-closed authority but providing
no diagnosis of repeated technical unknowns. The `.1` SQLite busy timeout is
not a deadline for the entire native status operation, which includes connection
and schema checks. Process creation, ownership registry writes and all other
shards share that supervisor turn. These are possible blocking or failure
locations to inspect, not verified causes of this CI failure.

`_spawn` does **not** wait for READY. `_record_process` directly writes the control
DB; it does **not** itself acquire the router's EX flock. Therefore the static
claim that spawning necessarily blocks on the selected worker's held SH flock
is unsupported. Other actual SQLite/process/scheduling waits would require
observed evidence. No supervisor exception banner appears in this raw log, but
absence of a banner is not evidence that its thread remained alive or scheduled.

## Required diagnostic distinctions

| Hypothesis | Observation needed | What must not be inferred |
| --- | --- | --- |
| Publisher entry expires before API | Original thread lease/time, original exception and API-call marker absent | This alone explains missing supervisor kill |
| Supervisor native observations remain unknown | Original status call start/finish, native exception attributes, thread stack and selected binding | Unknown permits kill, lease renewal, or healthy authority |
| Supervisor blocks or dies | Thread alive state, stack-only snapshot, mutex/pipe/process/registry location | An unobserved blocking path occurred in historical CI |
| Native expiry is observed for selected PID but exit misses horizon | Native PID/generation/expiry/now plus actual kill and pidfd timing | A component BUSY pass proves five-second recovery |
| Source/owner changes | Original PID/birth/boot, both worker identities, status generation/owner | A different owner grants permission to kill an unrelated process |

A single separately authorized original-case run can collect the existing
`_expired_gate_observation`, original exceptions, and periodic parent-thread
stacks using only filename/function/line number, never locals or raw financial
payloads. Wrapping the original native status call can record its original
start/finish, thread, monotonic/boottime, selected safe scalar fields and native
error attributes; it must rethrow the same exception and must not add database
reads. Include monitor alive/stop state and both worker identities, not only the
publisher. Record driver/source hashes, watchdog and whole-run budget, forced
cleanup and residual identities. Instrumentation overhead changes the observed
experiment; a non-reproduction must remain a non-reproduction.

The original five-second lease, five-second capture/recovery horizon, five-second
API phase and fifteen-second separate publication lifecycle stay distinct and
unchanged. No passing component or subsequent diagnostic run can relabel the
original CI failure. A fix requires its own concrete evidence, independent review
and fresh full-source gates; this review signs neither a five-second recovery
claim nor production readiness.

## Deployment and rollback

This is docs/evidence only, without schema, data, runtime or API changes. There
is nothing to deploy. Reverting these new review files must not delete or modify
original CI members, frozen source, private experiments, artifacts or clocks.
Source91 remains NO_GO and no real-funds or long-run approval follows.

## Concrete observation driver 5e26 review

The external candidate is `5e26f0acd04b47cdafad942464e70b537c70d30b`, following
`1ac5bb633e18634cb5e0a976ccd8efefb8af71ea`. Exact driver SHA-256 is
`81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee`.
Independent compilation/AST and 266 Git-blob hash checks passed without executing
the driver or importing the financial runtime. The original test and production
runtime bytes are unchanged. The status wrapper calls the original once and
returns or rethrows its result, without added SQL. Stack sampling excludes frame
locals; publisher error capture reads only its explicitly named errors cell.
The later candidate moved the whole timer before source preflight and records
the real interpreter/SQLite versions. Local Python3.13.5 is not CI's3.13.18.

There is no static blocker to **one separately parent-authorized CPU2/Python3.13
observation**, with these explicit conditions. Set outer `umask 077` and verify
the new output directory is0700; the driver does not itself set a private umask.
The27-second worker watchdog and reported30-second whole threshold do not impose
an OS-wide hard deadline on external IO. Final acceptance must independently AND
whole time, source hashes, logger/sampling health, observer-thread exit, no forced
cleanup or residual processes and the original outcome. Exit0 alone is insufficient.

The launcher discovers children from completed `spawn_return` records. A partial
original `_spawn` can fail after process creation but before that record, so an
empty recorded child list cannot prove no residual process. Check unmatched spawn
starts/returns and perform a read-only `/proc` scan for this new worker's PGID/SID
afterwards. No existing job may be signaled. Unknown sampling, observer failure,
watchdog, forced cleanup or residual state remains incomplete/NO_GO. A passing
original case is NO_REPRO of the historical assertion; it does not sign source91,
prove the five-second production claim, or establish the historical cause.

## Independent check of the unique observed run b570

The author preserved the unique run in
`b5707fe319cf4f07c64e34e8a62f130e5a135803`. Independent checker
`verify_actual_once.py` reads saved files, Git blobs and current `/proc` metadata
only. Its first execution passed31 narrow observed-evidence checks without
running any SQL, original test, new business command, native reproduction or
signal. All ten raw members match both the original private bytes and the
committed manifest;266 pre/post source entries match both approved5e26 and
base91 Git blobs. Actual local runtime is3.13.5/SQLite3.46.1, not CI3.13.18.

The one original case passed, hence **NO_REPRO**, in8.045662904 outer seconds.
The original323 status calls have one matching finish each, no status exception;
14 code-only samples observe supervisor and both workers. Three spawn starts
and returns balance, all three recorded children have pidfd exit and absence
records, and an independent current scan found no member of new PGID/SID230555.
The selected old PID230559 has an actual supervisor status record with expired
lease before its original kill call. The original two CIDs are SUCCEEDED and
the original financial conservation assertions were reached; this review does
not independently reopen a database or claim a full financial replay.

Time anchors must remain distinct. Capture to the original **parent's pidfd
exit observation** is4.753877499 seconds; publication-thread start to that same
observation is0.284567718 seconds. The separate10ms independent watcher observes
pidfd exit4.761417844 seconds after capture. These are observation times, not an
exact timestamp at which the kernel process exited. Reporting only the late
API-origin duration omits most of the intentionally awaited original lease.
The original five-second milestones passed in this run; the separate fifteen-
second publication lifecycle remains a distinct assertion.

**Strict observation-component evidence remains incomplete/NO_GO.** The approved
driver calls both observer `join(1)` methods but does not record their subsequent
`is_alive()` values. Worker/session exit proves no thread remains now, not that
both joins completed before worker exit. The author retained this missing
positive observation and the independent result preserves it. No value is
backfilled, no observation is repeated to wash it out, and no runtime fix or
release qualification follows from this non-reproduction. The historical CI
failure and its root cause remain unresolved.

## Static review of the proposed sixteen-sample lifecycle recorder

The next candidate is `8f25e9edcf2bcece056165ed911302a919893cac`, new helper
`trace_original91_lifecycle.py`, SHA
`48446ef1f9f0fbc1a70d4bbcd1b2c50ce844ad7aae2a5ae14249a9c3d4aa8e21`.
Its preregistration SHA is
`41cf484f9c0058e32bd9ec73a138ee6f146928600ec70fecde715d8ac0501e74`.
Neither the original81b9 helper nor its actual raw is modified. The new recorder
adds actual observer start/end/error events and post-join `is_alive` reads, private
umask/modes, current new-session metadata scan and explicit source/sampling/logger
flags. Status calls and original test assertions remain unchanged; no new SQL or
risk authority is introduced by these additions.

The final controller is not yet available, so this review cannot authorize the
batch. A concrete pure counterexample must be closed by that controller or a new
helper version: the helper's strict gate uses serialized worker completion flags
by truthiness and compares an error count with `==0`. Extracting only that AST
expression, a hypothetical worker report with completion string `"false"`,
errors `false`, zero tests, negative failures and nonboolean case status still
produces strict=true when the other synthetic technical fields are true.
Boolean or floating zero error counts are also accepted. This is a gate-shape
counterexample, not an observed native failure or forged actual result. Its
original pure red script/output are retained here.

Before execution, require exact boolean technical flags, exact nonboolean integer
counts, exactly one original case, valid failure/error counts and consistent case
outcome. Missing or inconsistent result fields are technical unknown and stop,
not an ordinary assertion failure. The external controller must independently
bind runtime/helper/source hashes, original result counts and actual environment.
B's executable path alone is insufficient: the prepared official build must use
its bound library directory and clear PYTHONPATH/PYTHONHOME. Matching Python3.13.18
still does not recreate CI's compiler, libc, image or scheduler.

For an immutable ABBA repeated four times, preserving ordinary assertion failures
and continuing the predetermined remaining slots is acceptable only after all
technical evidence/cleanup/runtime gates pass. Any error, unknown, corruption,
watchdog, observer failure or residual state stops; remaining slots must be
NOT_RUN, never replaced or added. Sixteen successes would remain NO_REPRO under
that design, not qualification. No native batch, SQL or original testcase was
executed while preparing this independent static review.

## Independent closure of the strict serialized-result validator

Candidate `7ce60c197a79f25dac887f352d35749386b812f9`, following `21b473a`,
adds a pure validator with SHA
`dbd32f4db11bb6449f63839e46595f574065b03026386dc362bc63f518a05c71`.
Independent pure controls executed only the audited78-line validator definition,
without importing the driver, financial runtime or SQL. The original four malformed
result vectors now refuse. Additional controls cover exact count/boolean types,
missing fields, one actual unskipped case, mutually consistent outcomes and
historical-stage flags, source identity, forbidden production approval, exact two
observer lifecycle records and aggregate consistency. Valid PASS and ordinary
assertion FAIL records can continue; a valid UNITTEST_ERROR or forced-cleanup
record requires stop. All26 first-pass controls passed and are retained.

This closes the earlier serialized-result shape finding for that validator. It
does not approve an entire controller. The controller must also bind the actual
test worker's recorded runtime, not only its preceding capability probe, and must
classify original cleanup kills from the event trace. For this fixed testcase,
normal expired-owner killing occurs in `uta-process-supervisor`; a MainThread
kill during `router.close` is forced cleanup even when the testcase's local
`cleanup_forced_kill` observation remains false. Verifying only an event-file hash
does not independently enforce that safety-stop policy. These concrete integration
conditions were sent to the author before any batch authorization. No batch ran
and no original raw result was changed by this review.

## Bound runtime/event controls and final whole-budget ordering finding

Candidate `1e6e7f7c35d9803b13358010d3e984b0acfc1567` adds the actual-worker
runtime contract and event semantics to new bound files, preserving older
proposals and raw records. Independent synthetic pure controls first passed:
10 runtime controls and12 event controls. They reject a B-labeled actual A
version, wrong executable/SQLite/loader environment/mapped library/hash, invalid
CPU/flag types, MainThread cleanup kill, missing expired ownership, wrong owner,
missing spawn/pidfd/postjoin records, live observer, sampling unknown, incomplete
status and invalid clock types. No actual native process or SQL was executed.
These close the specific actual-worker identity and cleanup-kill conditions for
the audited pure contracts; the actual batch pipeline remains unexecuted.

Root explicitly selected a diagnostic interpretation: a completely recorded
original business/supervisor native status exception is part of the observed
system, not itself a logger/sampler/source/result evidence gap. A paired original
status error may therefore be retained while the unchanged testcase continues;
it grants no healthy lease or financial authority. Any subsequent supervisor
kill still needs an original fresh expired-owner witness. Unittest ERROR or
logger/sampler/source/result incompleteness stops the batch; a technically
complete ordinary assertion FAIL preserves the fixed remaining order. The
independent event controls include this distinction explicitly.

One further concrete whole30 ordering defect remained in1e6e. Its finalizer sets
`whole_external_budget` before code hashes and new provider/binary/library posthash
reads. It later computes `safe` from that earlier flag, but records elapsed time
again. A pure extracted-finalizer control with synthetic time29.95s before a
synthetic hash and30.10s afterwards produces `all_checks=true` and
`DIAGNOSTIC_SAMPLE_COMPLETE` despite `whole_seconds=30.10`. The original script
and red JSON are retained; they do not represent an actual runtime overrun.

Before whole-batch GO, remeasure after all validation/hash work and use the same
final elapsed value for budget, safe and report. An additional outer sample-return
measurement must cover writing END and stop if that whole interval exceeds30,
retaining the original sample record rather than rewriting it. This is a timing
bookkeeping repair, not permission to change an original5-second assertion, add
samples or repeat a failure. No batch was run during this review.

## Final80fa clock closure and conditional diagnostic recommendation

Final candidate `80fae18c7afafdbb0145e5e8b44741323994b74f` binds controller SHA
`5ce9884cfd39238482c0282cf357aab52497b7fbacb395505eecb97f67eec15e`
and registration SHA
`e5b67407cc1ddec6e2b85bd96037649f8803d0e714b99ff15a95f867e717b13e`.
Independent Git-blob inspection confirms all seven registered dependencies match
their hashes, all266 original source entries remain unchanged, and the previously
reviewed result/runtime/event contracts, bound helper and no-SQL probe are byte
identical to1e6e. Earlier controls therefore still apply; no original red vector,
proposal, raw file or single-run result is rewritten.

The final controller remeasures after all verification/posthash operations and
uses one final elapsed value for sample budget, safe flag and report. Independent
pure extracted-code controls now reject the original29.95→30.10 hash-overrun
vector. A29.99-second on-time synthetic finalizer may pass. The caller also measures
through sample return, including original END writing. A synthetic END tail that
crosses30 stops after the first slot and marks the remaining15 NOT_RUN. The
original sample END remains unchanged and its exact hash is retained in the
separate OUTER-END record. END exceptions likewise stop. A technically complete
synthetic ordinary assertion FAIL follows all16 registered ABBA slots without
retries. All seven clock/caller controls first passed, with no native or SQL run.

There is no remaining concrete static blocker to **one exact, root-authorized
fixed16-sample diagnostic batch** under these bindings. This is a conditional
engineering recommendation, not execution permission from this review alone.
Require fresh private output, CPU2, registered per-process environment and actual
runtime checks, unchanged original windows and both watchdog/whole clocks. Stop
on technical evidence/runtime/source error, forced cleanup or residual state;
preserve every raw attempt and all NOT_RUN slots. Fully observed original native
status errors remain diagnostic observations under root's explicit amendment,
never healthy authority or permission to kill without a fresh expired-owner
witness. Unbound residuals are escalated, not signaled by guessed SID.

The actual controller and both real runtimes have not been executed by this
independent review. Remaining empirical behavior is deliberately pending. Sixteen
case successes would be NO_REPRO within this design; the historical CI failure,
source91 NO_GO and production acceptance stay unresolved. A captured failure is
retained by its original stage without authorizing an unreviewed runtime fix.
