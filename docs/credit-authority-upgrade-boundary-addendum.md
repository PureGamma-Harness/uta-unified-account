# Upgrade boundary addendum — inherited CID lookup and auth cut

This supplements `015f09b321a9fcf0dd7d8935093b90b1a68df497` after an independent
read-only design review. It changes no runtime, SQL or existing database. The
original 19-check model and its retained raw result remain unchanged. Its shared
`commands/events` arrays assume a global original-CID view; they do not implement
or prove that a new physical database inherits deduplication. Both mechanisms
below are implementation blockers. Production remains NO-GO.

## Original-CID directory and receipt resolution

An empty successor inbox is not evidence that a business command is new. Before
any new producer acceptance or financial admission, a future implementation
must consult a strongly consistent domain directory inherited across the entire
authenticated epoch lineage. Its key is the stable logical
`(domain_id, tenant_namespace, account_id, business_CID)`. Epoch, physical
authority, source transport ID, operation kind and payload hash are **not** part
of that key: changing kind/payload conflicts with the original command; changing
epoch cannot evade it. The tenant/account mapping must be explicit, immutable
and reviewed. V2's synthetic local actor is not evidence of a production tenant
mapping. Missing or ambiguous historical tenant mappings block import.

The directory's imported part is committed by the final old source/terminal
root and exact scope-to-domain mapping, including legacy receipts and declared
gaps. Existing business IDs/bytes are not normalized, shortened or renamed.
Each entry binds original kind and canonical payload bytes/hash, source ID,
acceptance state, original epoch/authority/scope/CID, receipt/terminal identity,
exact result bytes or an authenticated immutable location, journal/decision
references and the lineage root that proves ownership. Original bytes remain
unaltered. Receipt resolution cannot import old journal rows as new effects or
create new sources/decisions under an epoch-specific replacement ID.

The active directory requires a linearizable lookup-and-reserve operation for
the stable key. Its namespace is shared by all authorized adapters and epochs;
account/tenant isolation is enforced independently of lookup success. A
new-source reservation binds the active epoch, original request and one delivery
identity before delivery begins. Directory COMMIT and producer COMMIT are
separate when stored in different databases. A reservation whose producer
outcome is unknown stays unresolved; retry reconciles and delivers the same
request idempotently. It cannot expire into an absent key. The directory and
source cut must reconcile in both directions before retirement.

| Directory result for the stable key | Required POST behavior |
| --- | --- |
| Original terminal exists; kind/payload match | Return the original exact receipt after authenticated resolution; no new source, loan or journal |
| Original accepted/reserved/PENDING exists | Return/query the original unresolved status; reconcile its original epoch; no replacement CID/effect |
| Key exists with a different kind/payload/tenant binding | Conflict; no effects |
| Complete current directory proves absence and reservation CAS succeeds | Only then may the approved active epoch accept the new source |
| Directory, old-domain resolution, lineage root or mapping unavailable/unknown | UNKNOWN / deny new acceptance; a successor-local miss is never fallback proof |

If a verified copy of the original terminal bytes is already retained by the
directory, it can serve that original receipt without calling an unavailable
old process. Otherwise an unavailable old-domain read means UNKNOWN, not a new
loan. No fallback may infer absence from a failed read, empty local table or
timeout. The retirement-aware read path remains unimplemented; exact old normal
factories must still refuse retired inventories.

Add these proposed external schema fields to the earlier review packet:

| Object | Additional required fields |
| --- | --- |
| `UpgradeManifestV1` | `business_namespace_mapping_id`, `inherited_command_directory_root`, `directory_cutoff`, `directory_consistency_contract_id`, `receipt_resolution_contract_id` |
| Directory entry | `domain_id`, `tenant_namespace`, `account_id`, `business_CID`, `original_kind`, `original_payload_bytes`, `payload_hash`, `original_source_id`, `acceptance_state`, `original_epoch`, `original_authority_id`, `original_scope`, `receipt_id`, `terminal_state`, `result_bytes_or_authenticated_location`, `journal_refs`, `decision_refs`, `lineage_root` |

Actual acceptance must replay an old successful BORROW against a successor with
an empty local inbox and prove the original receipt returns with unchanged
aggregate loan/journal counts. Repeat for old rejection, PENDING, unavailable
old read, changed payload/kind, distinct tenant/account and concurrent requests
across adapters. An implementation that consults only the successor's local
tables must fail this test.

## AuthStore acceptance belongs to the pre-barrier cut

The future HMAC path adds an earlier boundary: AuthStore verification and nonce
consumption may have committed even though the financial source/PENDING has
not committed, or its result is unknown. Those already accepted grants/permits
must be enumerated and resolved. `financial PENDING count = 0` does not prove
the domain is drained. Current internal synthetic V2 has no implemented HMAC
first-source, cross-database revocation-epoch barrier or accepted-grant bridge;
this document does not claim otherwise.

The durable barrier must cover AuthStore acceptance plus all source adapters,
accepted-but-undelivered grants, nonce/acceptance outcome queries and financial
delivery permits. It needs a reviewed protocol relating auth acceptance epoch,
revocation epoch and domain epoch. A revocation race must be adjudicated by its
original explicit policy; the upgrade must not silently invent whether a
previously accepted grant remains executable. A missing epoch, missing grant
after nonce consumption, unknown COMMIT or unknown revocation result blocks the
cut. Neither TTL nor process-lease expiry recycles such a grant or its budget.

Each proposed `database_cuts` auth member additionally binds `auth_authority_id`,
`verification_policy_id`, `acceptance_epoch`, `revocation_epoch`,
`accepted_grant_cutoff`, `nonce_consumption_cutoff`, `accepted_grant_root`,
`nonce_consumption_root`, `revocation_root`,
`accepted_undelivered_grant_root`, `unknown_acceptance_root`,
`outstanding_delivery_permit_root`, and their exact counts. The overall manifest
also binds `auth_to_source_mapping_root` and `auth_barrier_contract_id`.
All unresolved/undelivered counts must be zero after original-policy
reconciliation, not merely omitted from the export. If no auth capability
exists, record explicit verified absence; do not invent zero rows for an
unqueried external AuthStore. Auth and source row roots/cutoffs must join both
ways with original IDs and hashes.

Required actual goldens include nonce COMMIT then crash before source delivery,
source COMMIT reply loss, duplicate grant delivery, revocation racing the
barrier, missing nonce/grant mapping and an auth database unavailable during
cutover. Independent AuthStore/HMAC review must accept these before production.

## Separate pure counterexample check

`scripts/model_credit_epoch_dedup_boundary.py` is a small, separate design check.
It demonstrates the successor-local-only lookup counterexample and checks that
auth accepted-but-undelivered/unknown epochs block the cut. It assumes the
directory and auth records supplied to it are authoritative; it implements no
index, CAS, signature, transport, database, account permission or HMAC runtime.
Its output is retained separately as
`credit-authority-upgrade-dedup-model-result.json`; it must not be combined with
the original 298-state/648-transition/19-check result as a new integrated run.

The separate CPU3/Python3.12 run at 2026-11-17
15:49:53.286357–15:49:53.286481 UTC passed with an external 3s watchdog,
16 directory scenarios and 12 auth-cut scenarios. Its local-only mutant creates
two total loan effects from one original CID; inherited lookup retains one and
returns the original receipt bytes. This is a pure counterexample, not an
observed defect in an installed successor implementation (none exists).
