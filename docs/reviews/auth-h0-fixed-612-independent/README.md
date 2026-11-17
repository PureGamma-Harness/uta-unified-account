# Independent fixed612 review: two payload fixes hold, new profile-audit integrity case is RED

Observed fixed runtime `61258109e10f4ea4609e03010d5f25716b2c4256`, materialized from retained Git into this independent sparse worktree. Only64 runtime files were needed; no full documentation clone or author runtime reuse occurred. Final909 and the original072/grant/revocation probe authorities and results remain unchanged.

The original grant/revocation payload defects are corrected within the exercised scope. **The overall retained-auth integrity acceptance remains blocked by a newly reproduced audit/profile association defect.** This is not a financial permission bypass. Every returned auth observation denied financial, source-delivery and execution authority, and there was no financial database, source/PENDING, native writer, endpoint, TLS or READY change.

## Source and test independence

Pure Git comparison shows that the fixed runtime modifies only `credit_auth_h0.py`: it adds `_config`'s call and the retained grant/revocation verifier. The shared MAC/nonce/legacy core in `request_signing.py` and compiled schema remain byte-identical to072. The verifier explicitly checks document key sets, types and values, preventing Python's `True == 1` equality from satisfying integer identity fields.

The [new independent probe](../../../tests/auth_h0_fixed_independent/fixed_data_probe.py) creates all authorities, profiles, grants and signatures through real public paths. Its signature reference constructs the published canonical array and HMAC literally; no production signer, parser, canonical-request helper, author test or verifier is used as an expected-value oracle. A separate [post-check](../../../tests/auth_h0_fixed_independent/read_fixed_results.py) independently rechecks22 exact retained private request MACs without exporting their keys, headers, nonces or signatures.

First actual batch was18:33:35.082633–18:33:35.563504 UTC on CPU4, outer monotonic480,874,288ns, exit1 under30 seconds. All64 runtime Git hashes and the new harness SHA were measured before and remained unchanged after. There was no repeat run to obtain a different result. Original private stdout/stderr, exact command, profiles, signed requests, authorities and before-corruption backups remain outside Git.

One earlier prehash failed because the no-checkout worktree's runtime files had not been materialized. That step ran no product subprocess and created no authority. Its PREPARATION_ONLY record is retained separately; restoring the exact existing Git files enabled the first actual batch above. No original failure was overwritten.

## Six exercised cases pass

| Independent case | Actual bounded result |
| --- | --- |
| Healthy old history plus unrelated profile1→2 advance | Old first acceptance remains byte-identical; a later real grant/acceptance uses profile2; current read and reopen succeed; all authorization flags false. |
| Grant payload replaced with `{}` | Reopen, current lookup, capture and control each reject503; no post-fault authority row changes. |
| Grant epoch encoded as JSON true while structured epoch is integer1 | All four paths reject503 with no authority mutation. |
| Semantically valid grant JSON with noncanonical leading space | All four paths reject503 with no authority mutation. |
| Revocation payload replaced with `{}` | Real revocation first denies borrow; after corruption all four paths reject503, with unchanged retained rows. |
| Grant's control-audit grant_id redirected to another existing grant | All four paths reject503, despite valid FK/schema, without authority mutation. |

Every corruption occurs only in a fresh independently owned authority, after removing and restoring its exact original immutable trigger. The [first result](first-fixed-source-observation.json) records complete operation outcomes; these are not reruns of the old072 failures or claims that all H0 tests passed.

## Seventh case: stale earlier profile revision is incorrectly accepted

The new case creates real profile1 and then commits real profile2 before it creates the tested grant. The original grant_created audit therefore has revision2. The probe changes only that audit row's `revision` from2 to1, then restores the original trigger. Catalogue rows and FK status are unchanged, as are all structured grants, keys, revocations and original first acceptance rows.

Fixed612 nevertheless reopens the authority, issues a current original-CID read, accepts a new auth CID and returns an existing control observation. Acceptance count increases1→2; authorization flags remainfalse. The [read-only completed-state check](read-only-and-crypto-postcheck.json) independently derives latest preceding profile revision2 from the unchanged profile audit sequence, while the tested grant-created audit now claims1. It verifies that this is the sole changed field among original audit rows; subsequent nonces/audits/acceptances append normally.

The cause is `_verify_grant_data`'s `any` earlier matching profile predicate. Existence of an older profile1 audit does not establish that profile1 governed a grant created after profile2 committed. Historical grants created before profile2 must remain valid; later controls must instead reference the latest preceding successful profile configuration. An equivalent predicate also exists for revocations, but this batch dynamically tests only the grant control, not a separate stale-profile revocation fault.

A future narrow correction should explicitly order profile controls by audit sequence or choose the maximum preceding sequence, then require that revision. It must preserve healthy historical profile advances and should separately validate both grant and revocation control points. The root controls that fix and its fresh retest. This review makes no runtime changes and does not repair the corrupt authority.

## Evidence and limits

Public [execution metadata](first-execution-public.json), [result](first-fixed-source-observation.json), [post-check](read-only-and-crypto-postcheck.json) and [raw identities](private-raw-identities.json) are explicit allowlists. Private argument positions become fixed placeholders; private streams and database bytes are not copied to Git. Exact actual requests and keys are available privately for these new independently created cases. The author's older per-request HMAC history is not independently proved from hashes alone; its original authorities have not been exhaustively reviewed in this fault-focused batch.

The two finished authorities in the new RED are read only through URI mode=ro, query_only, a read-only statement authorizer and one consistent transaction each. This establishes their completed-state relation, not historical lock ownership or real power-loss durability. Full legacy/API regression, actual profile-replace race, all quotas/handles/fork paths, full QA/CI/package, H1–H4, retirement, anti-rollback, HA, capacity and production remain outside this acceptance.

There is no deployment or migration from this review. Retain every original source, first outcome, acceptance and tombstone. Disable an experimental ingress rather than deleting its records or downgrading it to force another CID. No production or real-funds enablement follows.
