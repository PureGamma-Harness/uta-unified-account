# PR37: first integrated CI remains blocked

Frozen source `67cd9bd9fd494369b53c0a2792120c587d3e757f` has distinct first
attempt1 results: **all four push whole jobs passed; PR3.10/3.11/3.12 failed
unit and PR3.13 passed**. Each failed unit ran1,833 tests with one failure,
zero errors and zero skips. Push success does not replace the three PR failures
or qualify native recovery. No test or CI run was retried by this review.

| Run | Event | First terminal result |
| --- | --- | --- |
| [44229628066](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44229628066) | push | 3.10 / 3.11 / 3.12 / 3.13 whole jobs succeeded |
| [44229734501](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44229734501) | pull_request | 3.10 / 3.11 / 3.12 unit failed; 3.13 whole job succeeded |

[Exact jobs and unit/package step conclusions](../evidence/reviews/pr37-first-ci/run-job-outcomes.json).
All five successful whole-job claims use provider metadata only. No successful
unit, package, wheel or sdist archive was downloaded. Package steps in the
three failed jobs were skipped after their unit failures.

## Three first failed archives and source binding

Each failed job's decoded original log and unit archive was fetched once:

| PR runtime | Job | Artifact | ZIP bytes | SHA256 |
| --- | --- | --- | ---: | --- |
| 3.10 | 134551534625 | 14394098515 | 85,224 | `399e1f9ecd9b79f7435acddda01ed2cac28b317240fa467617b4901e2b6ac340` |
| 3.11 | 134551534178 | 14393934678 | 94,652 | `9e9748e23c36e6041456f663a3c700c5103c6c1a3c42bab1c14ce2ab9be1df4b` |
| 3.12 | 134551534526 | 14393979684 | 96,006 | `a4573bca4765be294bcaf65e2a56b8041b8be3d4408d0ceeb724d7cca8c56b46` |

All three ZIP sizes/digests match their provider records. Each contains exactly
summary.json, worker-result.json and unittest.txt; all nine member CRCs passed
and individual member hashes were recorded. Original ZIPs and complete members
remain private. [Integrity](../evidence/reviews/pr37-first-ci/artifact-integrity.json).
The PR artifact list was observed once when only the first failed311 artifact
was available, then once after all jobs terminated. These first-page snapshots
are separate; neither is silently replaced or claimed to enumerate all pages.
[Artifact metadata](../evidence/reviews/pr37-first-ci/artifact-metadata-projection.json).

All three runtime/summary records name actual PR merge
`f12852e79b9bbf26d598a75c19def8232f20e444`. Provider commit metadata binds
parents `[6010e920…, 67cd9bd…]` and tree
`10dd475784bebfddeaba703ebfbf3c9865d94619`, matching the exact local candidate.
All **356** before/after source digests agree across all three unit archives and
individually match the candidate Git blobs. Each complete unit-log hash also
matches its own summary. This is the unit-input map, not a whole-repository,
dependency or all-artifact qualification.
[Source binding and map](../evidence/reviews/pr37-first-ci/source-binding.json).

## Actual failure phase

All three failed logs contain the same assertion in
`test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`,
test_durable_faults.py:1456:

```text
AssertionError: bound child did not leave SH after undo within original capture horizon
```

This occurs after undoing an unsatisfied SH-capture stop: the bounded sampler
has not established the required eligible non-SH observation. The later
captured-success assertion, captured5s lease checks, unexpired-owner control,
queued held-gate command and publication/expiry recovery checks have not yet
been reached. The message does not retain the full capture-attempt vector or
registration trace. It therefore does not prove no kernel progress occurred,
identify the causal blocker or establish the new SPAWNED policy's effect.

Complete sanitized first failure sections remain separate:
[3.10](../evidence/reviews/pr37-first-ci/pr310.failure.sanitized.txt),
[3.11](../evidence/reviews/pr37-first-ci/pr311.failure.sanitized.txt),
[3.12](../evidence/reviews/pr37-first-ci/pr312.failure.sanitized.txt).
Unittest reported401.186s /309.726s /433.441s respectively; these durations are
test runs, not exchange latency or capacity measurements.
[Unit summaries](../evidence/reviews/pr37-first-ci/unit-summaries.json).

The failing test source is byte-identical to base6010. That is a source-range
fact, not a base reproduction or proof of harmlessness. No assertion, capture
window, original5s target or business threshold was changed by this review.
[Source-bound phase and limits](../evidence/reviews/pr37-first-ci/failure-phase-static-review.json).

## New conditional models and evidence-parser correction

All three new `SharedGateRegistrationProgressTests` methods explicitly report
`... ok` in **each** of the three failed logs: nine observed method results.
They use selected actual-method AST with fake clocks/registry/process objects.
They establish their conditional model checks; they are not new native
recovery executions or a5s wall-clock proof. The original16-case/14RED witness
and candidate24-pass fake-model results retain their original scope.
[Original new-method outcomes](../evidence/reviews/pr37-first-ci/target-method-results.json).

This review's first target-line parser rejected Python3.10's class-only
unittest display because it expected a parenthesized `.method` suffix. That
local AssertionError is separately retained. The corrected reader accepts
both display forms and checks exact method names against current source AST.
No original log, archive, test result or expected outcome was changed, and no
CI/test execution occurred again.
[First parser error](../evidence/reviews/pr37-first-ci/evidence-parser-first-error.json).

## Deployment and qualification boundary

This independent OWN adds safe evidence only. The runtime candidate changes
the SPAWNED registration transaction's shallow-copied database busy-handler
budget to min(original,.1), preserving the original shared database and other
events under its reviewed contract. A SQLite busy-handler setting does not
bound LOCKED/PROTOCOL behavior, internal retry, disk or OS scheduling. The
native5s recovery gate and the PR35 causal question remain open.

Original connector responses, signed download responses, complete logs and
three ZIPs remain outside Git in a0700 directory with0600 files. Public data
contains synthetic failure observations, source hashes and allowlisted
metadata; no key, nonce value, signed URL or database is published.
[Ownership and exact operation counts](../evidence/reviews/pr37-first-ci/review-ownership.json).

No runtime deployment, schema/data migration, service or signal operation
occurred during this review. Rollback removes only these new public records
and retains every first failure and financial history. Native recovery,
capacity, long-run stability, financial signoff and real-funds production
approval remain ungranted. Root owns integration of this evidence-only commit.
