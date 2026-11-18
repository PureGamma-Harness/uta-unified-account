# M04 first provider artifact: independent read-only evidence review

**Result: archive and recorded-metadata consistency verified; workload/capacity/production remain NO_GO.** This review covers only the first M04 run `44199787770`, job `134450614173`, attempt 1. The provider job failed at step 8. No retry, network request, artifact download, SQL, native worker, process signal, cryptographic helper, key or plaintext access was performed in this review.

## Immutable identities and artifact

Controller C is `8295aaca4b4d254c438b228bb9da5591dafceee3`; the actual manifest-only execution child M is `e643661dbafdff76e66c50d20eecc2fdef4bf9e1`, with sole parent C and only `config/independent-m0-approved.json` changed. The artifact's control/registration metadata, fixed Git marker bytes, controller/workflow/escrow-tool hashes and root's recorded single-push authorization agree. Root's push record reports one successful call, no retry and no unknown push result.

Artifact **14379489976** is **229,227 bytes**, SHA-256 `5a3c55507c5a3e5ffafe538d5f9ceaa46a6f5ec67171de8b7c750edf8b284712`. Its provider metadata, actual saved ZIP bytes, CRCs for all **13 unique members**, 12 manifest-listed member sizes/hashes and saved public originals match. No ZIP or CMS binary is included in this evidence commit.

The one CPU-3 read-only check had a 15-second subprocess bound and completed in **78,364,588 ns**, exit 0, empty stderr. Its internal metadata-check duration was 40,349,798 ns. [Execution record](../evidence/reviews/m04-first-provider-independent-20261117/first-execution.json), [first stdout](../evidence/reviews/m04-first-provider-independent-20261117/first.stdout) and [sanitized observation](../evidence/reviews/m04-first-provider-independent-20261117/observation.json) are retained. The reader itself is archived privately with its [byte/hash binding](../evidence/reviews/m04-first-provider-independent-20261117/reader-binding.json); no second execution occurred.

## Actual M04 failure evidence

The newly published D1 record is:

```json
{
  "kind": "M0_RESOURCE_DIAGNOSTIC",
  "version": 1,
  "phase": "CASE_B",
  "scope": "PRIVATE_ROOT",
  "operation": "ENTRY_LSTAT",
  "errno": 2,
  "catalogue_label": "AUTH_ROUTER_SHM",
  "unknown_relative_path_sha256": null,
  "primary_code": "resource_missing_non_aux"
}
```

Case B is **UNKNOWN**, complete outer duration **1.852508411 seconds**. Its recorded owner is PID 2604 / birth 3664; termination return code is -15, leader reaped and stdout/stderr closure recorded. Case P is **NOT_RUN**, because the first case did not pass. These are recorded provider observations, not processes reobserved in the local workspace.

The fixed controller's diagnostic catalogue maps this label to the router shared-memory sidecar under the case authority directory. Its missing-auxiliary classifier lists shard and runtime-probe sidecars but omits the router sidecar. That static omission agrees with this run's reported router-SHM rejection and supports the separately assigned code correction. D1 does not explain which operation removed the sidecar or establish a broader runtime fault.

This evidence applies to **M04 only**. M02 and M03 retain their original unlocated missing-resource failures. The new label must not be copied backward into those results. No workload throughput, profile or speedup result is available from this first failure.

## Authentication evidence: existing root attestation only

All four CMS stream members are present, and the escrow result records complete retention. This review reads only the two specifically authorized safe authentication JSON files.

The original root authentication observation records four successful authenticated containers and **45,307,693 ns** duration, with `stream_bytes` and `stream_sha256` mistakenly projected as null. Those nulls remain unchanged. Its addendum explains the field-name correction and records the same four streams as **zero bytes** with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; it records no second decryption. Both safe records remain separately hashed in the independent observation.

This verifies consistency of the root's attestation metadata. It is **not an independent decryption or inspection of a decrypted container**. No key, quarantine directory or plaintext was read. Empty streams do not establish that the driver never started, and recipient encryption alone does not authenticate the sender.

## Source provenance and count discrepancy

The source remains `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`. Its **1,090,482-byte** source manifest, SHA-256 `1809df3a938df00a3156490d7d1e2fec74a17d2d3f28d96172c63ddd851bd296`, contains 5,518 entries and is byte-for-byte equal to the retained M03 source manifest. The prior full Git binding is reused through that exact-byte identity; this review **did not recheck all 5,518 Git blobs**.

One bookkeeping discrepancy is preserved: root's `public-verify-first.json` reports `file_count=14`, but its own file-digest map and the ZIP contain **13 files**. All 13 digest-map values agree with the actual archive; root's verifier exit was 0 with duration 85,473,613 ns. The standalone count field must not be cited as evidence of 14 files. This review neither overwrites that first record nor conceals the mismatch.

## Deployment, rollback and remaining gates

This commit publishes only sanitized documentation, JSON observations and textual hashes/outputs. Original provider wrappers, raw logs, ZIP/CMS bytes, private reader, authenticated-container material and secrets remain outside Git. No runtime, service, schema, parameter, active long test or financial authority changes.

A separately reviewed router-sidecar classifier correction may receive a newly labeled pure validation. This failed M04 execution remains immutable; no repeat execution is authorized by this report. Revert this evidence commit to withdraw the public report while preserving original records. Successful metadata retention is not order/liquidation capacity, a six-hour or 24-hour stability pass, financial replay or production approval.
