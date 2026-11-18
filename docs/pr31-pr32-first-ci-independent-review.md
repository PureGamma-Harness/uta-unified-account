# PR31 and PR32: independent first CI observations

This report preserves the first observation at **2026-11-18 00:14:03 UTC**, followed by first job metadata at **00:14:27 UTC**. **PR31's two runs failed. PR32's two runs were still in progress**, with no conclusion at those observation times. Pending is not failure or success.

No CI run was retried or dispatched. No test, CLI, SQL, worker, actual long-run inspection, observer or audit was executed by this review. Original provider responses, logs and the two downloaded failure ZIPs remain in a 0700 directory with files protected as 0600.

## Separate invocations and source bindings

| PR | Head | Event / run | First observed outcome |
|---|---|---|---|
| 31 | `56ecb87faa656901de9fd359f95014157d9c5585` | push / 44204771130 | completed / FAILURE |
| 31 | same | pull_request / 44204885012 | completed / FAILURE |
| 32 | `497c67f60901653634a96f629087f805032acec5` | push / 44205495492 | in_progress / null |
| 32 | same | pull_request / 44205859502 | in_progress / null |

All are attempt 1. Both PRs use base `6010e920a168b35fccfc9ef9ee34e030b28b11d9`. Actual synthetic merges are `1a56d2507de88b5ff97284e1e339c346bcbe0cf1` for PR31 and `c95e5e77edcdaa2f9454bad00517f1ff970cad66` for PR32. Each merge has the recorded base/head parents and the same tree as its source.

Both heads and the base have identical product `uta/` tree `4a0d5a989f0d7112454e41bbdb0162ffef34dbe4`. PR31's metadata binder retains `REVIEW_AUTHORIZED=False`; PR32 records a test-only CLI shutdown observation and does not establish a shutdown-cause fix. Tree equality does not prove that new CI failures are harmless, caused by metadata changes, or equivalent to old failures.

The three test source blobs relevant to PR31's failures are unchanged from the base. The [first machine-readable observation](../evidence/reviews/pr31-pr32-first-ci-20261118/first-observation.json) records these bindings, all 16 jobs, exact assertion contexts, time budgets and missing observed fields.

## PR31 push: two Python 3.13 publication/activation failures

Push job **134467778551** failed its unit step. Its **1,853** tests had **two failures**, no errors/skips. The other three push jobs succeeded, including their package steps. The failed job skipped packaging.

Both failures are in `ManagedRouterReadReferenceTests`:

- `test_pending_partial_publication_does_not_claim_a_local_market_commit`, caller line 631 → `activate` line **548**: the same original snapshot is published with timeout 8 seconds, and the returned `publishing` is still true. This occurs after releasing the remaining held shard fence, before activation or the later financial-ready poll.
- `test_real_partial_fanout_stale_and_recovery_remain_explicit_through_http`, caller line 583 → `activate` line **549**: publication has already returned `publishing=false`, but `set_kill_switch(False, timeout=8)` still returns `halted=true`. The final five-second readiness loop and intentional stale-market segment have not yet been reached.

Original fixture parameters are a **two-second quote age**, three-second native lease, 0.01-second poll interval and 0.03-second background interval. The deliberate external fence lasts five seconds. The partial-fanout case waits up to two seconds for an actual owner before timestamping its first tick; both cases use the same original snapshot through completion. Initial partial publication timeout is 0.25 seconds, original local receipt wait is one second, completion publication and activation each have eight-second API budgets, and HTTP reads have a four-second timeout.

The failing assertions supplied no response payload. Actual per-shard receipts, rejection reason, owner identity/lease and tick age at the failing call are absent from the failure message. A stale-quote or readiness explanation is plausible only as an unverified hypothesis; it is not a demonstrated cause or a financial reconciliation failure.

## PR31 pull request: Python 3.10 initial worker-identity failure

PR job **134468167118** ran **1,853** tests with **one failure**, no errors/skips. The other three PR jobs succeeded, including packaging. The failed job skipped packaging.

`ManagedPartialLiquidationTests.test_managed_partial_liquidation_survives_real_worker_kill_and_reconciles` reaches `tests/test_managed_liquidation.py:105` via line 74. Immediately after initial start, publication and activation, it calls `diagnostics()` and requires every worker's PID to be present, distinct from the parent PID, and equal to `owner_pid`. That predicate fails.

The preceding assertion established two distinct PID values. The failure occurs **before the first opening order submission**, so this invocation has not reached the worker kill, partial liquidation execution or final financial reconciliation. The original configuration uses a **0.6-second lease**, 0.01-second polling, 0.05-second background interval and the unchanged 30-second default quote age. Publication and activation each have a 12-second budget; the immediate diagnostics call has the unchanged one-second default timeout. No owner-ready wait separates activation from this identity assertion.

The actual worker rows were not attached to the assertion. PID/birth/generation, the precise mismatching row, lease validity and the diagnostic read timestamp remain evidence gaps. This report does not choose a race, timeout or financial cause.

## Preserved artifacts and missing observations

Two failure ZIPs were each downloaded once:

| Run | Artifact | Bytes | SHA-256 |
|---|---:|---:|---|
| PR31 pull request | 14383109020 | 84,830 | `97b43b9272bf66e41c0845f654290dc46b9fffccfea2cb0415d47cc00cb19d27` |
| PR31 push | 14383372325 | 94,874 | `83ef2a716839e62eb964f4f22991b54508b7e148e8b582a821eeba259b75cd5e` |

Provider digest/size, all three member CRCs, unittest digest and each of the **357** before/after standard source-map Git blobs were independently verified. The PR artifact reports the actual merge; the push artifact reports its source head. Successful-job unit and package ZIPs were not downloaded.

Each ZIP has only summary, worker-result and unittest members. Fixture phase observations are held in memory and optionally written when `UTA_READVIEW_PHASE_EVIDENCE` is configured; the fixed CI workflow does not set it, and case-specific phase bodies are not preserved in these artifacts. Other tests' diagnostic rows cannot be reassigned to these failures. Passing earlier assertions establish control-flow boundaries; they do not supply an unrecorded native snapshot.

These three assertions form three separate first-failure groups. They must not be collapsed into the old expired-SH failures or dismissed under a metadata-only scope.

## PR32 pending boundary and next observations

All eight PR32 jobs were in progress when fetched, and their package steps were pending. No completed PR32 failure artifact was inspected at this first snapshot. Later natural completion is a new labeled observation; this historical pending record must remain unchanged. No waiting or rerun is required to manufacture a conclusion.

## Deployment and rollback

This commit contains only sanitized documentation and JSON evidence. It changes no runtime, test assertion, lease, quote TTL, API timeout, schema, parameter, controller or active process. Preserve original failure bytes and missing-field disclosures before adding diagnostic instrumentation in a separately reviewed source.

Revert this evidence commit to withdraw the report while retaining original records. No merge, deployment, real-funds enablement or gate override is authorized. Production/capacity approval remains false; the long-run acceptance is a separate ongoing task.

## Later PR32 natural-completion observation

At **2026-11-18 00:21:21 UTC**, a separately labeled follow-up GET found both original PR32 attempt-1 runs completed with **FAILURE**. The first 00:14 pending snapshot above and its original JSON remain unchanged. No CI execution was retried.

In each run, Python 3.12 succeeded; Python 3.10, 3.11 and 3.13 each failed their unit step and skipped packaging. Each failing suite ran **1,840 tests with one failure, no errors/skips**. All six failures are the pure preservation-evidence assertion at `tests/test_cli_sigterm_failure_evidence.py:201`: `test_original_business_case_is_preserved_except_documented_observation`. They are not failures at a native CLI shutdown assertion.

The test removes specified observation hooks, returns `ast.dump(method, include_attributes=False)`, hashes that representation and compares it to the single fixed digest `a5884f2d24313698722277f803206c460aa1ef7e2a38055dfdae7820df01d128`. The committed digest record declares no Python-version or cross-version AST serialization contract. Both 3.10 and 3.11 runs report actual digest `2668cdf7dada1b19bc7a87396fad2893265b8d5654579f05f9039b36817abc98`; both 3.13 runs report `3bf36241a88c82a67a2381c0cc1b737343a01885efb90f09794e4295160305b5`. The two 3.12 jobs succeeded. This identifies a version-dependent evidence-test contract for review; it does not establish a business-method change, explain the earlier CLI shutdown failure, or justify removing the preservation requirement.

The six newly failed unit ZIPs were each downloaded once. Provider SHA/size, all three member CRCs, unittest hash, equal before/after source maps and all **355** standard Git input blobs per ZIP were independently verified against head `497c67f60901653634a96f629087f805032acec5`; PR artifacts report the bound synthetic merge. No successful-job ZIP or package ZIP was downloaded. [The later observation](../evidence/reviews/pr31-pr32-first-ci-20261118/pr32-natural-completion-observation.json) records all run/job IDs, artifact hashes and exact observed digests.

This follow-up performed no normalization experiment, test rerun, SQL, CLI, worker, long-run action, CI trigger or code fix. PR31's three distinct first failures remain open, and all production approval remains false.
