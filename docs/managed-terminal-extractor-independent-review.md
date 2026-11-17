# Independent review: managed terminal metadata extractor

Reviewed candidate `7e5a6aeeb151ecc1b327320798d18c6113316294` against the frozen producer/supervisor source `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`. **NO_GO for using the current candidate field as a qualified terminal evidence gate.** This review does not report a financial exploit or a failure of the running six-hour job.

## Scope and observed first results

Only the extractor's fixed Git blob, tests, documentation and original supervisor/observer source were read. A separate tiny worktree and fresh temporary fake JSON trees were used. No real run files, database, private clone, process signal, observer, cold audit, native worker, financial command or load were touched.

The first local invocation failed before importing the candidate because the new no-checkout sparse worktree had not physically materialized the extractor. The full original stdout, stderr and execution record remain. Restoring exactly the pinned Git blob corrected that input setup; no candidate code or test expectation changed.

The first actual six fake-file cases then ran once on CPU 3 under a ten-second process bound: **six tests, five failures and one passing negative control**, 0.007 seconds unittest duration, 90,006,422 ns complete subprocess duration, exit 1. [Execution](../evidence/reviews/managed-terminal-extractor-independent-20261117/corrected-input-once02-execution.json), [original stderr](../evidence/reviews/managed-terminal-extractor-independent-20261117/corrected-input-once02.stderr) and [independent cases](../evidence/reviews/managed-terminal-extractor-independent-20261117/first_negative_controls.py) are retained separately from the initial pre-import error.

The extractor's financial, continuous-six-hour, 24-hour, full replay, capacity and production flags remain explicitly false. The defects below concern `candidate_for_independent_terminal_review` and its apparently all-true observed gates, which can currently qualify inconsistent or failed metadata for terminal review. They do not change those hard false flags.

## Finding T1: receipt presence is treated as successful execution

`FILES` reads producer and strict cold result JSON, but `summarize` ignores both contents. A regular JSON object `{}` satisfies the required observation gate. Likewise `{"exit_code":1,"stdout_complete":false}` for both receipts does not prevent candidate=true.

The source's actual `Pipes.result()` at `tools/run_managed_long.py:235–252` supplies exit code, original child identity, completion time, stdout digest/completeness and a filtered response. These fields are available for checking. The source's terminal workflow at lines 490–538 records the producer, then final-before, strict cold audit, final-after and summary in that order. Presence alone cannot establish that chain succeeded.

The “only progress and summary exist” negative control correctly stays false. However, adding empty producer/cold objects and a coverage status string changes it to true without any identity or cold receipt.

## Finding T2: final-before/after and audit receipt binding are absent

The extractor does not read `control/final-before-cold.json`, `control/final-after-cold.json` or `observer/producer-cold-audit-receipt.json`. A fake pair with differing checkpoint watermarks and an audit receipt whose hash disagrees, and whose audit pass is false, still produces candidate=true when the summary booleans are true.

The actual observer's `final_check` at `tools/managed_soak_observer.py:623–689` checks stopped original driver/listener/worker identity, cold authority, logs, original contract, stable financial/checkpoint watermark, independent reopen and cold receipt. It returns the watermark and producer audit digest. The cold audit receipt at lines 788–794 contains before/after watermark, frozen commit, audit SHA, audit scope and producer runtime. The standalone extractor currently binds none of these raw observations.

A summary copied from a different stage or task can therefore supply positive booleans without independently proving the underlying identity or watermarks. A bounded reader should expose missing/unknown/mismatch explicitly, or keep the candidate gate false pending a separate reviewed binding step.

## Finding T3: fault and original time facts can conflict

The progress record enforces exactly 180 worker and 18 parent fault counters using integer type checks. That is useful, but summary fields `actual_fault_signals` and `fault_schedule_complete` are ignored. A fake summary with worker=179 and fault_schedule_complete=false still qualifies against progress worker=180.

The extractor only checks progress's own elapsed seconds, source code string, planned rounds and controller-session count. It does not bind the original boot, start/deadline, job identity, actual controller terminal identity or observer contract digest. The fake “wrong original contract” case intentionally puts a short conflicting contract in an otherwise unread `job/job.json`; it demonstrates that this file is entirely outside the extractor's checks. That fake `contract` object is **not a claim about the producer's actual job.json schema**. Static reading establishes that the original observer derives its contract from job configuration/environment plus checkpoint state at `validate_metadata` lines 313–335, and emits original start/deadline and a contract digest in its final response. A correction should use that actual schema and bind the final responses/registered launch, rather than copy the ad hoc fake object as a production contract format.

No observer uptime, current wall time or delayed collection may make up a short producer duration. The original source's measured producer duration and original 21,600-second contract must remain distinct.

## Properties retained

The code rejects malformed/non-object JSON, duplicate keys and nonfinite JSON literals; file reads have size bounds and reject leaf symlinks/nonregular files. The documentation explicitly requires a trusted upper directory and acknowledges reads do not form a consistent database snapshot. The progress checks reject Boolean counts, extra round states, missing errors, missing required records and sub-21,600 durations without epsilon. No UTA or SQL module is imported.

These observations do not establish authentic raw metadata, stopped process status, a complete event replay or a validated trading platform. Worker/parent counts must remain facts corroborated by the original reconciliation evidence, not inferred fault-attempt counts.

## Requested correction and next review

Preserve all original first results. Either keep the candidate field unconditionally false until a separately reviewed terminal-binding pass, or add fail-closed checks using the actual original result schemas: successful complete producer/cold/final-before/final-after receipts, original process/boot/source/contract identity, terminal order, equal snapshot watermarks and valid matching audit digest/runtime/scope, cross-consistent fault totals, and collection/coverage error absence. Missing, unreadable, malformed, unsuccessful or inconsistent evidence must remain UNKNOWN/NO_GO.

Any corrected fake run should use a new output set, retain the five red cases and add a schema-accurate complete-chain positive control. It must not rerun the real six-hour task, start another observer, execute cold SQL audit or acquire any financial authority. The current supervisor remains the unique owner of natural terminal collection. A schema-compatible extractor must also account for final-before legitimately lacking the not-yet-generated producer receipt.

## Deployment and rollback

This independent review adds only evidence and documentation. It changes no runtime, schema, API, parameter or active process. Revert the review commit to remove the report while keeping private/original failed evidence. Do not deploy the reviewed candidate as an acceptance gate until these evidence-binding defects are reviewed. No real-funds enablement is authorized.
