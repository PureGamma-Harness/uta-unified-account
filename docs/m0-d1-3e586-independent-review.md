# D1 independent first counterexample: failed complete prefix is published

Fixed controller candidate **`3e586f99c4ed750766461d4212cd17d9501cea84`**, SHA256 `66cd5dd05a080cfde3e08614be2cc8cbbaef36e7c93689b592c7775be2e0e3be`, is **NO_GO pending diagnostic commit/publication closure**. The first independent pure batch produced one positive and one RED; no original candidate or raw result is modified.

## Reproduction and actual behavior

The independent fixture uses tiny owned0700 directories, ordinary synthetic files and fake I/O failures. It triggers a real annotated missing-path failure through the controller's `_resource_lstat` and `resource_health_check`, with a synthetic secret/path sentinel. It then injects EIO at file fsync, PermissionError at quarantine rename, and PermissionError at prefix deletion. The full JSON bytes were already written before the fsync failure. **The fixture does not rewrite that leftover file to malformed JSON.**

The original risk failure remains `resource_missing_non_aux`, with its original FileNotFoundError context, and the write status is correctly `UNAVAILABLE`. However, `collect_resource_diagnostics` reads the leftover full JSON, accepts its schema, returns **COMPLETE** and adds one record. The subsequent manifest is accepted by **verify_public=true**. Thus a failed optional write prefix is promoted to a valid published record despite the writer's explicit commitment rule and its comment that failed prefixes must never be published as valid records.

The normal comparison case reports RECORDED, COMPLETE and verify_public=true as expected. Both cases preserve all four original driver/case-owner byte streams. Neither record leaks the raw synthetic secret or root path. The financial/risk UNKNOWN is not upgraded; this finding concerns the diagnostic commit/collection contract, not a funds exploit or new evidence of M03's unknown cause.

The author's existing double-failure test writes `{partial` into the public path after the failure, then tests malformed-file rejection. That negative control covers malformed leftovers but misses the naturally complete valid-JSON prefix left by fsync failure. Strict JSON/schema validation alone cannot distinguish that failed prefix from the successfully committed record. A fix must preserve trusted failure/commit state through collection, reject or leave unlisted every known failed prefix, preserve the original primary, and cover every recording call site. This review supplies evidence rather than implementing that fix.

## Original independent evidence

The first batch ran `2026-11-17T22:55:25.402585+00:00` to `22:55:25.597896+00:00`, CPU3 with10s watchdog/ResourceWarning as error, elapsed195308343ns, exit1. Source-bound fixture SHA256 is `e4643f1f973b89b1478caa47346b263a4ed815ee03ab5c72b2cce5ceb9bef71f`. Its complete source/stdout/stderr/execution hashes are retained under `evidence/reviews/m0-d1-3e586/`.

```sh
taskset -c 3 timeout 10s python -B -W error::ResourceWarning \
  evidence/reviews/m0-d1-3e586/first_prefix_boundary.py
```

This is a definition-only controller import plus tiny-file/fake I/O control check. It performs no SQL, product import, actual native/owner process, crypto, network, service, signal, M04, CI or workload execution. It does not repeat154 author tests. Other public-schema, budget and static invariants remain to be checked or carried forward after the fixed revision; this first finding is not represented as their full independent acceptance.

The original candidate, original M03 B UNKNOWN/P NOT_RUN/three available ciphertext facts, unresolved missing path, and all earlier first-failure evidence remain unchanged. Root and the author received this concrete counterexample before the evidence commit. No next diagnostic load or production action is authorized. Rollback is to keep the previous control candidate unactivated while retaining all first evidence.
