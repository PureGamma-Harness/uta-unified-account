# Explicit public M0 files in the source distribution

The source distribution must retain the repository's public diagnostic workflows and recipient certificate. Fixed code `f3a45ade08e63bc99f224017d79b31da9236d840`, based on `1d727b9d8e121611d0227dbee162192c13a76769`, adds exactly these three explicit `MANIFEST.in` includes:

- `.github/workflows/independent-m0.yml`
- `.github/workflows/independent-m0-once.yml`
- `config/m0-stream-recipient-public.pem`

There is no general PEM/key glob. The certificate is public; no private key is selected. No controller, test, resource policy, budget, workflow content, namespace or execution marker changes. This base does not contain the spent M04 approved marker. No push, M05 or CI trigger was performed.

## Original evidence and resulting scope

The first general CI for M04 source `e643661dbafdff76e66c50d20eecc2fdef4bf9e1`, run 44199787800, failed at unit tests in all four runtimes; package checks were **NOT_RUN**. That immutable result is preserved in evidence commit `dc9e42ababfd29106129d85ecd00ae4c38ebbb8c`. The three paths were a static packaging-selection gap there; this change does not claim an old-source package failure report or rebuild that source.

The changed-source **local packaging-only** build and exact archive verifier passed once. The native recovery and import-test failures remain separate open work. There was no full unit rerun, installed CLI test, SQL, owner, financial command, cryptographic operation, network request or deployment in this validation.

## Actual first invocation and resource admission

Actual CPU affinity was CPU 4. The batch bound was 180 seconds and each subprocess stage was limited to at most 120 seconds. Immediately before full materialization:

- Available disk: **18,527,903,744 bytes**.
- Fixed cohost reserve floor: **17,716,740,096 bytes**.
- Complete source file/directory allocation estimate: **170,242,048 bytes**.
- Additional build-peak reservation: **524,288,000 bytes**.
- Required fresh free space: **18,411,270,144 bytes**.

All **5,839** tracked files were physically materialized, verified against exact Git blob identities and SHA-256 recorded before the backend ran. Actual source allocation matched the estimate. Post-materialization available space was 18,355,892,224 bytes, exceeding the floor plus build reservation. No threshold was lowered.

| Stage | Actual seconds | Exit | Timed out |
|---|---:|---:|---|
| Full sparse-checkout materialization | 1.019054382 | 0 | false |
| Explicit complete-source restore | 0.175419309 | 0 | false |
| Wheel and source distribution build | 8.756833553 | 0 | false |
| Existing exact archive verifier | 24.031178588 | 0 | false |

Complete batch duration: **34.871726960 seconds**. All tracked input manifests before/after were byte-identical, and each input was again checked against Git after verification. Final free space was 18,294,833,152 bytes.

[Admission](../evidence/m0-public-package-f3a45ad-first/admission.json), [materialized input facts](../evidence/m0-public-package-f3a45ad-first/materialized-input.json), [actual first result and argv](../evidence/m0-public-package-f3a45ad-first/first-result.json), [full archive manifest](../evidence/m0-public-package-f3a45ad-first/artifact-manifest.json) and [source/original byte bindings](../evidence/m0-public-package-f3a45ad-first/source-and-originals-binding.json) are retained. Binary archives, backend output and full input maps remain in the external permission-restricted evidence directory.

The measured source is the fixed code commit above. Later documentation/evidence commits are not relabeled as having been built by that original invocation.

## Archive acceptance

All seven existing checks passed: version, exact wheel runtime, exact source runtime, every required source path and byte, pinned/licensed legacy fixture and entry points. The source distribution contains all **5,839** required tracked files without missing or mismatched contents. Both archive formats contain the exact **62** runtime files: **61 Python modules and one HTML asset**.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 357,465 | `53ab818ba6225de89b74c3a8a047a93aca905df6d7d7a31c54814835267ad178` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 43,733,261 | `a6b0d24cb9c3fe25023e97281774c3caa54eeda7afd1c3cd1e75e5dbca113ad4` |

The source-distribution verifier compared the three added public files and every other tracked path byte-for-byte to the frozen checkout. These are packaging results, not throughput, risk-model validation or production authorization. Independent cross-group archive review remains a separate recorded step.

## Reproduction, deployment and rollback

Use a clean complete checkout at the fixed code commit. Build with the existing local setuptools backend, writing archives outside the checkout, then run `tools/verify_release_archives.py` with `--source`, the exact `--commit`, `--wheel`, `--sdist` and an external `--output`. The preserved argv and runtime/toolchain versions identify this first invocation. Reproduction is an explicit new invocation with new outputs; it must not overwrite this evidence.

Distribute only reviewed artifacts whose hashes match the release record. The three repository support files are source-distribution contents; adding them does not execute a workflow or authorize a diagnostic. Installation or real-funds deployment was not performed and is not approved by this packaging result.

Rollback the code commit to remove the three explicit source-manifest includes, or restore a previously reviewed artifact. No database migration, accounting compensation or process restart is required by this manifest-only change. Preserve the original CI failures and this first changed-source result through rollback. Production approval stays false.
