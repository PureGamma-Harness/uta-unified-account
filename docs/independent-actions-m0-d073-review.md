# Independent resource-scan review: d073022 first RED

Fixed candidate `d07302252736ab7cb8a9338078b913ef33e728c0` has controller SHA256 `57fc60bc914264d1fbd4d0b5c907222f3743ebbbbb332af30f8d043cec90302c`. Verdict: **NO_GO pending explicit private/root-role scoping of SQLite auxiliary recovery**. No M03, branch, push, SQL, workload, crypto, observer or native execution was authorized or performed by this review.

## Independent first counterexamples

The first independent batch at `2026-11-17T21:16:18.625228+00:00` to `21:16:18.792962+00:00`, CPU3,15s outer watchdog, elapsed167752191ns, exit1, produced one positive and two RED controls. Original source, stdout, stderr and source-bound timing/hashes are preserved under `evidence/reviews/independent-actions-m0-d073/`.

Each case creates tiny synthetic regular files, unlinks an enumerated auxiliary immediately before its nofollow `lstat`, and calls the real `case_bytes(private, public, 'B')`. It imports only the controller's definition-only module and standard library; no SQLite or product implementation is imported.

| Case | Required result | Actual d073022 |
|---|---|---|
| `private/B/workload/authority/shard-0000.sqlite3-shm` | Retry known private auxiliary; count main1B | PASS, returns1B |
| `public/case-B-safe/B/workload/authority/shard-0000.sqlite3-shm` | Reject public disappearance | **RED**, retries and returns1B |
| `private/B/P/workload/authority/shard-0000.sqlite3-shm` | Reject unexpected nested P layout inside B | **RED**, retries and returns1B |

The candidate's documentation says public and unknown layouts do not qualify. However, `tree_bytes(root)` treats every root as a private-layout anchor. `_sqlite_aux_location` always tries full-private `[BP]/workload/...` and `runtime-probe/...` patterns, then additionally tries `workload/...` whenever the anchor's basename is B or P. Therefore public safe trees can borrow the private exemption, and a case subtree accepts layouts intended only relative to the full private root. The requested minimal repair is explicit anchor context: full private root, exact private case subtree, or no auxiliary exemption for public trees. This review does not modify the production candidate.

The preceding aggregate `resource_usage(private, public)` check rejects these public/nested unknown layouts when that scan encounters their disappearance. Thus these findings concern the subsequent independent case-metering window and the stated strict context contract. They do not establish a financial exploit, a completed trade, or the unique cause of original M02. M01 and M02 remain permanently failed; B UNKNOWN/P NOT_RUN is unchanged.

## Static invariants retained

Compared with previously reviewed e466b67, only existing functions `tree_bytes`, `case_bytes` and `resource_usage` change; seven new resource helper functions are added. Other existing function ASTs, including the two business argv templates, `budget_spec`, case56+2+2/60 watchdog handling, receipt/population parsing, four-stream escrow, and registration verification, remain identical. The controller changes the once-only branch/ID to distinct03. The once workflow's source ref is unchanged at full40hex909; workflow changes retarget the branch/if gate and include the new pure test file. No old run/branch may be reused.

The AES256GCM strict-DER escrow module remains byte-identical with SHA256 `89f48b50d22a1b8c5898ed9413ad6bc2567f6cd30c0a58626d0921f5e91ec83e`. Source909/tree, recipient, two argv, case32MiB/normal64MiB/escrow96MiB/cleanup32MiB, total192MiB plus2GiB fresh-space floor are unchanged. The template still has execution_authorized=false and a zero control commit. Fixed C contains no `config/independent-m0-approved.json` execution marker. Distinct03 is preparation only, not approval.

The source now explicitly propagates walk errors, caps attempts at3, anchors retry time at original entry+50ms, validates stable paths/types across retries, charges regular per-path high-water sizes, and rejects incremental compartment excess. This batch is deliberately limited to the two newly found context gaps and one legal-layout positive; the author's131 pure tests and provider artifact collection were not rerun. Their originals, fixture errors, earlier sidecar RED and StopIteration records remain retained in the candidate history.

Reproduce the independent first findings without any financial runtime:

```sh
taskset -c 3 timeout 15s python -B -W error::ResourceWarning \
  evidence/reviews/independent-actions-m0-d073/first_boundaries.py
```

This command is source-bound to d073022's controller hash. A later fixed revision needs an explicit adapter and new output files; the first RED must remain byte-identical. Capacity, HA, reliability, production and real-fund approval remain false.
