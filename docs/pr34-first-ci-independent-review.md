# PR34 integrated source: first CI independent review

Frozen source `8d6e7852689851f56801768de65506242f9d4c46` has distinct first
results: **push passed all four whole jobs; PR failed Python3.12 unit with two
failures, while the other three PR whole jobs passed**. Both runs are attempt1.
The successful push does not replace the PR failure or grant production
approval. No test or CI run was retried by this review.

| Run | Event | First terminal result |
| --- | --- | --- |
| [44217784215](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44217784215) | push | 3.10 / 3.11 / 3.12 / 3.13 whole jobs succeeded |
| [44217846755](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44217846755) | pull_request | 3.12 unit failed; 3.10 / 3.11 / 3.13 whole jobs succeeded |

[Exact job IDs, unit conclusions and first terminal metadata](../evidence/reviews/pr34-first-ci/run-job-outcomes.json).
Success claims are provider whole-job metadata. No successful artifact ZIP,
push artifact metadata or push ZIP was fetched. Pending observations were
retained separately from terminal observations; none was rewritten as success.

## Failed artifact and exact source binding

Only failed PR3.12 job `134512043520` supplied a downloaded unit archive:
artifact `14389736273`, **95,159B**, SHA256
`8319cce1677ddac774b26e4f6530ea4d8b7f673798ec4a4a45b021d74f3a5a02`.
Its provider size/digest match the one actual download. The ZIP contains exactly
summary.json, worker-result.json and unittest.txt; all three CRCs, member sizes
and hashes were verified before parsing. The original ZIP and members remain
private. [Integrity](../evidence/reviews/pr34-first-ci/artifact-integrity.json).

The artifact records actual merge checkout
`6d7b65d53be96d4e344fc4daba85b87ed2dafbc3`, also present in the original decoded
job's runtime and unit summaries. Independently fetched provider commit
metadata binds its parents to `[6010e920…, 8d6e785…]` and its tree to
`f1007c2e26df1f96f01e9c7deb19e61b0416fdad`, the local candidate's exact tree.
All **354** before/after source hashes agree and individually match the
candidate's Git blob bytes; the complete log's hash matches summary.json.
This is the declared unit-input map, not verification of every repository
file, success artifact or runtime dependency.
[Full source map and binding](../evidence/reviews/pr34-first-ci/source-binding.json).

PR artifact metadata was fetched once, first page only, returning ten items.
Only the failed unit archive was downloaded; this review does not claim a
complete artifact enumeration or inspect the successful packages.
[Metadata projection](../evidence/reviews/pr34-first-ci/artifact-metadata-projection.json).

## Actual failures and the new contract checks

The failed job used Python3.12.16 / SQLite3.46.1 and ran **1,835 tests / two
failures / zero errors / zero skipped**, worker exit1. Unittest reported
452.805s. [Unit summary](../evidence/reviews/pr34-first-ci/unit-summary.json)
and [complete sanitized failure section](../evidence/reviews/pr34-first-ci/failure.sanitized.txt).

1. `test_malformed_missing_and_oversize_persistent_quotes_fail_closed` fails
   at test_process_readiness.py:162, during its initial activate() call.
   wait_ready rejects the explicit non-transient market_stale observation.
   The intended malformed/missing/oversize quote loop has not yet started.
   The retained diagnostic includes worker generations, lease/owner states
   and unchanged publication identity; it does not prove a scheduling cause.
2. `test_same_version_changed_persistent_content_is_not_reused` reaches its
   final recovery activation, then fails the immediate financial_ready
   assertion at line158. That assertion retained no diagnostic payload, so
   this review cannot equate its cause with the first failure.

The relevant failing test and readiness-helper sources are byte-identical to
base6010. That is a scope fact, not a baseline reproduction or proof the new
runtime check is harmless. No timeout, TTL, assertion or acceptance threshold
was changed. [Source-bound phase review](../evidence/reviews/pr34-first-ci/failure-phase-static-review.json).

All **five** new `BatchDispositionContractTests` methods explicitly report
`... ok` in the same complete failed log. Their result is scoped to this
invocation and their selected-method contract; it does not turn the two
readiness failures green or supply new malformed-record SQL recovery tests.
[Original target-method results](../evidence/reviews/pr34-first-ci/target-method-results.json).

## Preservation, deployment and rollback

This independent OWN adds only safe evidence and this report. It changes no
runtime, tests, CI workflow, risk rule, schema or authority. The original two
baseline RED, author26 and independent1,694 results retain their original
source and scope. The new integrated first CI is recorded separately.

Provider responses, signed download response, complete decoded job log, ZIP
and original members remain outside Git in a0700 directory with0600 files.
Public material contains synthetic diagnostic data, allowlisted metadata,
source hashes and a sanitized full failure section; no signed URL, key,
database or nonce value is published.
[Operation counts and ownership](../evidence/reviews/pr34-first-ci/review-ownership.json).

There is no deployment or migration for this evidence-only change. Rollback
removes only these added public records and must retain all private originals
and financial history. Integrated acceptance remains blocked by the PR failure;
capacity, long-run stability, HA/DR, financial signoff and real-funds production
approval remain open. No local SQL, UTA module, worker, service or signal action
occurred during this review.
