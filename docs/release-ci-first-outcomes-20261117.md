# PR25–27 first CI outcome review

Independent read-only review of the first push and pull-request runs observed on 2026-11-17. **NO_GO.** No workflow was rerun or dispatched. Successful jobs remain evidence for their particular invocation; they do not erase a failed invocation.

## Observed runs

| PR | Source | Event / run | First outcome | Failure |
|---|---|---|---|---|
| 25 | `6010e920a168b35fccfc9ef9ee34e030b28b11d9` | push / 44184136107 | FAILURE | Python 3.11 unit tests |
| 25 | same | pull_request / 44184574093 | SUCCESS | All four jobs succeeded in this distinct run |
| 26 | `244b2005b2c2c0757905ab1a4b48508957b04f4d` | push / 44186589062 | FAILURE | Python 3.12 unit tests |
| 26 | same | pull_request / 44186740016 | FAILURE | Python 3.13 unit tests |
| 27 | `37ac3198e9412c7edf89a7842d876fe8113ff68b` | push / 44187794849 | FAILURE | Python 3.12 unit tests; other three jobs fail packaging |
| 27 | same | pull_request / 44187905394 | FAILURE | All four jobs fail packaging |

All six runs were completed, attempt 1; all 24 jobs were completed. In total, 13 jobs succeeded and 11 failed. This is the observed cohort, without a retry or a claim that the overall release gate passed.

## Three newly inspected unit failure artifacts

Each of these ZIPs was downloaded once, checked against the provider's SHA-256 and size, and passed CRC verification for all three members. Their original summary and unittest bytes remain private. The summary's unittest hash was independently checked. Every input in its before/after source maps was checked against the corresponding source commit's Git blob.

- PR26 pull-request Python 3.13: artifact 14373744588, 95,519 bytes, `debda28df3cf6f6818fae47e5b11cf6b9761f554eb0324a8cdecdf40793fd069`. **1,846 tests, one failure, no errors/skips**, 414.295101102 seconds outer duration; 358 input blobs checked. The existing natural capture case `test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover` fails at `tests/test_durable_faults.py:1456`: “bound child did not leave SH after undo within original capture horizon.”
- PR26 push Python 3.12: artifact 14374658132, 94,843 bytes, `f42ca526e87c25c9cf5e70afada499aa2f4ad0e89837be3832ffaf2f9de182a2`. **1,846 tests, one failure, no errors/skips**, 396.941077889 seconds; 358 input blobs checked. `test_market_probe_rejects_a_real_expired_owner_lease_without_retry` fails at `tests/test_readiness_sampling.py:253`: expected one wrapped diagnostics call, observed four.
- PR27 push Python 3.12: artifact 14375093746, 95,078 bytes, `d2cd841f614442676951bb027d255b90f93099d52a4c25c755268b895952229a`. **1,851 tests, one failure, no errors/skips**, 429.309788556 seconds; 355 input blobs checked. The natural capture case fails at the same assertion as PR26's Python 3.13 run.

The Python 3.12 “four calls” failure is a separate observed symptom. Static reading shows an interval between the earlier expired-owner observation and the subsequently wrapped diagnostic call. The code rejects a currently observed inactive owner immediately; a supervisor may change the observed owner state during that interval. This is an unverified timing hypothesis, **not** a demonstrated cause, a reason to weaken the assertion, or evidence that the production command path retried financial work. Native diagnosis remains open.

PR25's earlier Python 3.11 failure and its independently archived ZIP remain unchanged. This review fetched its job metadata and decoded job log but did not download or requalify its ZIP again.

## Seven package failures

All seven jobs that reached the package check reported:

```json
{
  "checks": {
    "version": true,
    "wheel_runtime_exact": true,
    "sdist_runtime_exact": true,
    "sdist_required_files_exact": false,
    "legacy_fixture_pinned": true,
    "legacy_fixture_licensed": true,
    "entry_points": true
  },
  "sdist_missing": ["deploy/review-manifest.template.json"],
  "passed": false
}
```

These reports were read from the seven original decoded job logs. Their package ZIPs were **not downloaded or independently binary checked** here. This is a concrete source distribution omission, independent of the native capture failure. The failing source commit must retain its original result. A one-line manifest fix, separately identified and built, may close the packaging omission without resolving the native failures.

## Source and merge identity

The provider commit metadata independently binds PR26's source and synthetic merge `555833eb28c70cc1e0ea1ca801563145a47c36f7` to tree `5e98060e57ff252a482b7781b381957c61a6c505`. PR27's source and synthetic merge `ea2082c242ec6bb0a0f272a77a4e9d5ddc26a333` both bind to tree `375866b43236218ffc3ea919427216f3ef5a8cb4`. Their merge parents match the PR25 base and respective source.

The unit summaries report the expected actual checkout: PR26 pull-request merge, PR26 push source, and PR27 push source. Tree equality does not guarantee identical scheduling or execution state.

## Evidence scope and handling

[Machine-readable observations](../evidence/reviews/release-ci-first-outcomes-20261117/observations.json) records all six runs, 24 jobs, 57 artifact metadata records, the three binary-checked unit ZIPs, source-map checks, the seven package reports, and hashes of private originals. The wrapper exposes the first page; each actual run response had four jobs and no more than 12 artifact records. Only the three marked unit ZIPs were independently binary checked in this review.

Raw provider responses, decoded full logs, downloaded ZIPs, and file-service download references remain in a permission-restricted directory outside Git. No download reference, key, signature, nonce or credential is included in public evidence.

The first local summary reader failed because its regex was malformed, after the first ZIP had already been downloaded and authenticated. Its original code and failure record remain. A separately named corrected reader reused those saved bytes and downloaded each other ZIP once. This was an evidence-reader error; no test, CI job or business operation was rerun.

## Remediation and release gates

Keep the original failures immutable. Review and build a minimal manifest correction separately. Independently diagnose the natural capture and owner-observation failures without inflating deadlines, weakening assertions, or replacing the natural case with a controlled one. Preserve source/runtime/market/version provenance and actual process termination evidence in any newly approved native experiment.

No SQL, worker process, trading command, liquidation, performance load, deployment or financial activation was executed by this review. Long-duration and capacity acceptance remain separate gates. **Production approval stays false.**

## Deployment and rollback

This is a documentation/evidence-only commit and changes no schema, package configuration, service or runtime behavior. Reviewers can reproduce metadata inspection with the six run IDs and compare the recorded SHA-256 values to the retained originals. Revert this evidence commit to withdraw the report; retain all private originals and earlier failed outcomes. This report does not authorize deployment or replacement of an active writer.
