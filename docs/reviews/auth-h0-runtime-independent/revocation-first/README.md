# Independent revocation-payload integrity negative: first actual result RED

Observed original runtime remains `072cc77c5a96b48c81a143020ab8ac6c9a794a9b`. This is a separate new, self-created authority and probe after the earlier grant-payload RED. It does not change the earlier result, the author's original twelve-case passes or any original author database.

Actual first probe:18:13:33.653535–18:13:33.966103 UTC, CPU4, outer monotonic312,637,378ns, exit1 under a30-second bound. All64 runtime files in the independent review worktree were checked against retained Git072 before the child and remained identical after it. Materializing those original tracked runtime files avoided racing the author's separate fix work; no runtime file was edited.

The [new independent probe](../../../../tests/auth_h0_independent/revocation_payload_corruption.py) uses real public constructors and its own literal canonical-array/HMAC implementation with random private key/profile and nonces. It creates borrow/read/repay grants, obtains an initial auth-only observation, and performs a real grant revocation. A new BORROW request is correctly rejected403 before corruption, proving the original tombstone is effective. This is not a mock or a fabricated granted principal.

The sole offline fault is replacing one `auth_credit_grant_revocations.payload` with canonical `{}` and restoring its exact original immutable trigger. All catalogue rows and FK status remain unchanged. The observed original implementation then:

- Reopens that authority through real `CreditNonceStoreV2` and a new ingress.
- Returns the existing read-grant control observation.
- Returns the original first acceptance through a fresh currently authorized read.
- Accepts a new CID under the separate still-valid REPAY grant, increasing auth acceptances1→2.

The revocation row itself remains present. This does **not** demonstrate revival of revoked borrow permission. Every observation's financial/source-delivery/execution authorization staysfalse, and no finance or network action exists. The failed expectation is refusal of contradictory retained revocation evidence.

The [read-only post-check](read-only-postcheck.json), using the [independent checker](../../../../tests/auth_h0_independent/read_revocation_probe.py), checks two finished self-created authorities with URI mode=ro, query_only, a read-only statement authorizer and one consistent snapshot each. Exactly one revocation-table field differs; all key and grant rows, original audit rows and original first acceptance rows remain unchanged. Counts change nonces2→4, audit7→9, acceptances1→2, matching the subsequent read and repay-intent authentication. Both exact catalogues and FK checks stay unchanged/clean.

There was one preceding preparation error: `git sparse-checkout add --no-cone` is unsupported for add, followed by a missing-source prehash. That step created no authority, imported no product and performed no MAC. Its [PREPARATION_ONLY record](preparation-only-error.json) is retained separately; correcting the checkout enabled the first actual probe above. It is not a product failure or a discarded corruption result.

Allowlisted [observation](first-red-observation.json), [execution metadata](first-red-execution-public.json) and [raw identities](private-raw-identities.json) contain no actual key, nonce, signature, request or database contents. Exact private commands/streams/requests/keyfiles/current authority and original backup remain at the indicated private root. Earlier grant-probe raw files were all rehashed and remained byte-identical. No private raw stream is copied to Git.

H0 data-integrity acceptance of072 remains blocked. A future correction must validate canonical revocation descriptors and actual audit/revision links without rewriting tombstones or historical payloads. It also needs to distinguish JSON booleans from integer identities; exact canonical expected bytes are preferable to Python dict equality, where True equals1. That is an implementation caution, not another executed failure. Any retest belongs to a separately pinned fixed source and a fresh owned authority; these original results are never overwritten. No financial, complete H0, production, capacity or HA approval follows.
