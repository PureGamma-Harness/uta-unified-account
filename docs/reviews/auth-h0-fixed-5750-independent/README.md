# Independent5750 review: accept the exercised auth-integrity fixes only

Observed fixed source `5750e12d60dbf7f8414b4e837e076a60c93a23bc`. **Accept the scoped H0 retained grant/revocation payload and latest-profile association fixes exercised here.** This is not full H0, final909, financial, production or capacity acceptance. All observations retain literal false financial/source-delivery/execution flags. No financial authority, source/PENDING, native writer, TLS/listener, public route or READY transition is involved.

The original072 and612 failures, their source-labelled scripts and private authorities stay unchanged. This review uses a new source-labelled harness, new sparse worktree and new private authorities. It does not repair or reopen the original bad authorities with a new product constructor.

## Source boundary

[Pure Git comparison](static-source-scope.json) verifies the runtime change from612 is only `credit_auth_h0.py`. The fourteen-line diff replaces the earlier `any` matching profile predicate with a same-held-connection MAIN query selecting successful profile controls strictly before the event, explicitly ordered by sequence descending with limit1. Both grant and revocation audit checks use it. The shared signing/nonce/legacy core and compiled schema bytes are unchanged.

The independent sparse worktree contains the64 exact retained runtime blobs. All were hashed before and remained byte-identical after the actual probe; no author worktree import or ongoing-edit race is involved. The [new probe](../../../tests/auth_h0_fixed_5750_independent/fixed_data_probe.py) uses actual public constructors and a literal canonical-array/HMAC reference, not the author's tests or production sign/parse/verifier functions as its oracle.

## Actual first independent batch

First actual execution was18:48:42.898451–18:48:43.427645 UTC, CPU4, outer monotonic529,198,140ns, exit0 under a30-second bound on the shared host. It ran eight declared cases once; all eight passed. Original raw streams, exact command, keys/profiles, exact signed requests, authorities and before-fault backups remain private. Public [outcomes](first-fixed-source-observation.json), [execution metadata](first-execution-public.json) and [raw identities](private-raw-identities.json) use explicit allowlists.

| Independent case | Actual observed behavior |
| --- | --- |
| Healthy profile1→2→3 advances with unrelated added keys | Original first acceptance stays byte-identical; accepted histories retain revisions1/2/3; current original-CID lookup and reopen work. |
| Grant payload replaced with `{}` | Reopen, lookup, capture and control each reject503 before any authority row change. |
| Grant epoch JSON true versus structured integer1 | The same four paths reject503 without mutation. |
| Noncanonical grant payload whitespace | The same four paths reject503 without mutation. |
| Revocation payload replaced with `{}` | Real prior revocation denies borrow; all four paths then reject corrupt history without mutation. |
| Grant audit bound to a different existing grant ID | All four paths reject with unchanged restored schema and clean FK. |
| Grant created after profile2, audit revision changed2→1 | All four paths reject; this closes the equivalent fresh version of the original612 failure. |
| Revocation after profile2, audit revision changed2→1 | All four paths reject. This is a new fixed-source case; it does not claim an earlier612 revocation variant was dynamically reproduced. |

Each fault changes exactly one independently owned database field after removing/restoring its original immutable trigger. Full catalogue/FK state stays unchanged. The seven damaged authorities keep their damaged data; successful refusal is not repair or historical rewriting. Their first acceptance counts remain1 after all refused operations.

## Independent completed-state and MAC checks

The [separate checker](../../../tests/auth_h0_fixed_5750_independent/read_fixed_results.py) uses no product imports. It opens only finished independent authorities using mode=ro, query_only, a read-only statement authorizer and a consistent transaction per file. Its [result](read-only-and-crypto-postcheck.json) independently compares canonical grant/revocation descriptors, actual control-audit identities and latest preceding profile revision. Before-fault copies are valid; damaged copies retain the expected inconsistency and exactly their pre-probe rows. Healthy history retains profile and acceptance revisions1/2/3.

It independently recomputes27 exact private request MACs using the retained bodies, headers and private profile keys. Those requests were generated and immediately passed to real capture/lookup calls by the probe. This does not claim every request consumed a nonce: the integrity failures correctly refuse before nonce mutation. No actual key, nonce, signature, request or database byte is published. The author's older per-request MAC history remains unproved by this check.

One metadata field in the original driver incorrectly labels `python_runtime` as `30s`, from indexing the timeout argument. That original record remains unchanged; the [erratum](execution-metadata-erratum.json) identifies the actual interpreter at command position5. The first child did not itself record its full sys.version. A subsequent real post-check using that exact interpreter reports Python3.12.14, SQLite3.53.1 and CPU4. This is explicitly post-check metadata, not a replacement first-run record. No functional probe was repeated to correct the label.

## Scope and remaining gates

The [verdict](scope-verdict.json) accepts only these source-bound fixes and observations. It grants no full H0 rollout or production permission. Exhaustive legacy/API regression, author-original authorities, profile-replace competition, the complete quota/handle/fork/UNKNOWN matrix, full QA/CI/package/install and H1–H4 remain unverified here. HA, anti-rollback, large fault domains, sustained capacity and real-funds approval remain open.

No runtime deployment, data migration or repair is performed by this review. Preserve original accepted identities, audits and tombstones. Any future enabled experimental authority must be disabled and forward-corrected rather than deleted, downgraded or assigned a new business CID to erase uncertainty. Final909 and all existing jobs/source pins are untouched.
