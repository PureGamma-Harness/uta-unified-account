# Independent M02 first-run evidence closure

The original once02 run **44172126501, attempt 1** is permanently **FAILURE**. B is **UNKNOWN** and P is **NOT_RUN**. This review preserves that outcome; it approves no further execution, capacity, HA, production use, or real funds.

## Immutable identities and original evidence

| Identity | Actual value |
|---|---|
| Reviewed control C | `e466b67faba5fb586d68f8bd35fb7f9c7a63336e` |
| Execution marker M | `07c3dc6c3d8a6cbd239e3463b55f8904cac99340` |
| Qualified workload source | `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` |
| Provider job | `134353729679` |
| Provider artifact | `14366519733`, `independent-m0-safe-44172126501-1` |
| Original ZIP | 228850 bytes; SHA256 `1ae12dfbdb8f7798b6579de4d6988bb0628a481320f7d7e04e98b000d3f290d4` |

Provider job/artifact metadata was read through the GitHub plugin. The run's attempt, timestamps and source identity were obtained using the read-only GitHub run API, because the plugin projection did not include those fields. The original ZIP remains private at `/workspace/uta-m0-once02-independent-provider/artifact-14366519733.zip`; no signed URL, credentials, ciphertext binary, private database, or private key is committed. Its nine JSON members are preserved byte for byte under `evidence/reviews/independent-actions-m0-once02-first-run/`. This includes the original 5518-file source manifest, not a substituted manifest from another attempt.

The independent reader checked provider size/SHA256, CRC of every ZIP member, exact unique member names, all manifest member sizes/hashes, and each archived JSON's original bytes. It verified M has C as its sole parent and adds only `config/independent-m0-approved.json`, whose bytes match the control record. Controller and escrow source hashes match C. All **5518 source-map entries / 149342893 bytes** match the source commit's Git blobs; Git tree is `cee60bc0b5413551030300e065d0dcaac6a7ff55`.

## What ran, and what remains unknown

The actual source checkout, runtime setup and pure-control steps succeeded. The execution step failed; subsequent public-allowlist verification and artifact upload succeeded. This differs from M01, whose malformed checkout ref prevented execution and produced no artifact. M01 run `44169093697` remains failed and distinct from M02.

M02 published the successful runtime capability probe: Python 3.12.14, SQLite 3.45.1, WAL, synchronous FULL (`2`), no replication. OpenSSL 3.0.13 passed the strict public-recipient CMS capability check. These probes establish neither financial B completion nor a throughput result.

B's owned case worker **PID 2606 / birth ticks 9324** started. After **1173100276 ns** of outer time, the health/resource gate reported `ENOENT` while reading `B/workload/authority/shard-0000.sqlite3-shm`. Cleanup reports `UNKNOWN`, TERM return code `-15`, leader reaped, and closed stdout/stderr. The original controller's `tree_bytes` walks directory names and then calls `lstat` without a disappearance policy; a transient SQLite sidecar disappearance is consistent with this observed gate failure. The public record does not expose the financial driver PID or establish the exact financial subprocess/settlement boundary. No claim that the driver or two native owners never started is justified.

P was not run after B's UNKNOWN result. There is no accepted B/P summary, 200-arrival population, capacity result or speedup. The original failed execution must not be retried or replaced by a future run.

## Four-stream retention and independent review limits

The original artifact contains the four closed B stream ciphertexts and reports successful escrow; it explicitly does not claim every transitive native stream or authenticated sender origin. Escrow PASS leaves financial B UNKNOWN.

Root separately performed the first offline strict-DER, authenticated OpenSSL decrypt and exact-container binding/hash checks. Its only authorized public observation, preserved unchanged as `root-public-decryption-observation.json`, has SHA256 `9305ed86655f66004cddf83ad4721d4d44a88070baf15d2da5d1cb1c69dcb9e6`. It attests that **all four actual authenticated stream bodies are zero bytes**. This reviewer cross-checked the observation's source/C/M/run/attempt/artifact identities, recipient SPKI and each ciphertext size/hash against the original provider archive. This reviewer did **not** read the actual private key, quarantine, or plaintext, and did not independently decrypt. Empty streams do not prove that financial execution never started or completed any particular operation.

## Reproduction and result

From the evidence worktree:

```sh
taskset -c 3 timeout 15s python evidence/reviews/independent-actions-m0-once02-first-run/read_first_result.py \
  --zip /workspace/uta-m0-once02-independent-provider/artifact-14366519733.zip
```

The first reader run passed at `2026-11-17T20:56:42.285374+00:00` to `20:56:42.992399+00:00`, outer elapsed **707037158 ns**, exit 0. Original stdout, stderr and source-bound execution metadata are retained. This is file/Git/ZIP and public-attestation verification only: **zero SQL, product imports, financial native executions, decryptions, workload starts, or Actions changes**. Any later resource-enumeration fix requires separate immutable CODE/PURE review; no M03 or further native execution is authorized by this evidence.
