# Independent H0 runtime review: extra grant-payload integrity negative is RED

Observed runtime `072cc77c5a96b48c81a143020ab8ac6c9a794a9b`; author evidence head `b483050f7034f1275ba4f1c104ffad81060ab397`. This additional independent negative failed its required refusal. **The H0 integrity acceptance is blocked.** The author's original twelve passing methods per runtime retain their original result; this independent probe does not relabel them.

This is an auth-only retained-evidence consistency defect. Every first/query observation continued to set financial, source-delivery and execution authorization to literal false. No financial authority, source/PENDING, loan, repayment, native execution, network endpoint or READY transition was used or enabled. Final909 and the author's original databases and outputs were unchanged.

## Actual first observation

The [independently written probe](../../../tests/auth_h0_independent/grant_payload_corruption.py) uses public real constructors and a fresh private AuthDB. It creates a random private key/profile and manually implements the published canonical request array and HMAC using standard-library primitives. It does not call the production sign_headers/canonical_request helpers or the author's tests as an oracle. Actual signed capture first succeeds and produces one auth-only acceptance.

The probe then backs up its own completed authority. In this self-created copy's active path, it drops only the grant no-update trigger, changes one borrow-grant `payload` to canonical `{}`, recreates the exact original trigger and commits. Full MAIN catalogue rows remain byte-for-byte equal and `foreign_key_check` is empty. No original author authority is modified.

The expected result is refusal of inconsistent retained grant evidence. The actual sequence is:

1. A real `CreditNonceStoreV2` constructor reopens successfully.
2. A new real issuer and a fresh literal-HMAC/current-credit.read query issue an auth_query_only observation.
3. A fresh literal-HMAC capture under a new CID issues another auth_first_observation.
4. Acceptance count increases from1 to2 while the corrupt grant payload stays present.

The original assertion fails with `AssertionError: grant payload corruption was accepted despite normative full grant payload equality`. First actual execution was18:05:58.920825–18:05:59.158258 UTC on CPU4, outer monotonic237,438,465ns, exit1 under a30-second watchdog. There was no retry, fix or rerun to obtain a different result.

The [allowlisted result](first-red-observation.json) and [execution metadata](first-red-execution-public.json) retain this outcome. Private raw streams, exact command, actual requests, key/profile, current AuthDB and before-corruption backup remain outside Git. Public command metadata replaces only the predefined private/result argument positions; no raw request or secret is regex-redacted and published. This document and the probe contain no actual key, nonce or signature values.

## Independent completed-state checks

The [read-only checker](../../../tests/auth_h0_independent/read_grant_probe.py) opens only the two finished independently created authorities with URI mode=ro, query_only=ON, a read-only statement authorizer and one consistent transaction per file. Its [post-check](read-only-postcheck.json) verifies:

- Both catalogues are identical and both FK checks are empty.
- Exactly one grant-table field differs: the selected grant payload.
- All key and revocation rows, original audit rows and original acceptance rows are unchanged.
- Auth nonces change1→3, audit rows4→6 and acceptances1→2, matching the subsequent query and new capture.
- All64 current runtime files match the actual Git blobs of072cc77, and source HEAD is b483050.

Runtime per-file binding was measured after the first probe; the first driver did not record a separate pre-import per-file snapshot. That limit is explicit rather than backfilled. The observed source was clean before independent work and no source edit was made. The read-only post-check is additional completed-state evidence, not a second corruption-probe run.

## Cause and required correction boundary

`CreditNonceStoreV2._config` verifies complete schema and FK structure, while `_grant` uses structured grant columns without checking canonical grant payload equality or its original control-audit content. `_first` verifies its acceptance payload/audit but does not validate that retained grant descriptor. The mandatory H0 refinement requires full profile/grant payload equality; the unused payload can therefore become internally contradictory without refusal.

A narrowly scoped future correction should validate retained grant/revocation canonical payload fields and actual audit/revision relationships on load and use, within the auth authority. It must preserve original evidence, retained IDs/tombstones and legacy format1 behavior. It must not repair the corrupt record, drop the marker, rewrite history, make the observation financial permission or change final909. The root controls any fix and necessary retest; this review changes no production code.

This evidence does not prove a financial authorization bypass or defeat the trusted-binary/OS-owner boundary. It is a reproducible integrity fault with unchanged schema, relevant to the claimed retained-data verifier. Other original data, schema, thread/fork, quota, race, legacy and unknown-result paths still require independent scope-specific validation. No overall production, HA or capacity approval follows.
