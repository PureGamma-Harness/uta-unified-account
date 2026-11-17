# Credit authority upgrade / rollback operator decision manual — proposal

This manual accompanies `credit-authority-upgrade-protocol.md`. No commands
below activate anything: the required migration, retirement, intake barrier and
epoch coordinator are not implemented by current V2. Today the supported choice
for a published authority is recovery using its exact retained artifact/runtime
and original CIDs. Production and real funds remain NO-GO without independent
implementation review and explicit trusted-operator/financial approval.

Apply `credit-authority-upgrade-boundary-addendum.md`: new POSTs require inherited
global original-CID lookup, and the drain includes AuthStore-accepted grants and
nonce COMMITs not yet delivered to financial source/PENDING. A local empty inbox
or zero financial PENDING count is insufficient. Both bridges remain unimplemented.

## Prepare a concrete review packet

Record the frozen old and proposed new actual source/runtime artifacts, domain
and physical authority identities, canonical paths, all producer/financial
database identities, policy versions, unique handoff ID and original allocation
claim set. Retain executable deployment files and dependencies for every
historical segment. A manifest without the matching actual runtime is not a
recovery package. Do not use the new build's existing factory to assert that the
old database is valid: exact old code pinning also applies to normal read joins.

The packet must include the complete per-asset original raw audit, old-root and
successor-opening commitments, golden/differential reports, intake and retirement
proofs, handoff certificate, independent approvals, backup/restore validation
and the exact proposed coordinator transitions. It must describe each current
gap as a gap. No secret token/nonce/private database is copied to public evidence.

## Execute only after the missing mechanisms are accepted

1. Commit the domain-wide intake barrier and stop every source adapter,
   including REPAY and any funding/interest producer. Keep read/status queries
   available where verified. Enumerate pre-barrier permits; resolve unknown
   acceptance by original source/CID at its original database.
2. Deliver all previously accepted sources under their original identities.
   Drain financial FIFO using the exact old runtime and a real current lease.
   Query unknown financial outcomes; reconcile source, inbox, intent/audit,
   complete journal, credit receipt and terminal both ways. Do not create a new
   CID, return UNKNOWN budget or mark PENDING rejected by elapsed time.
3. Require zero unresolved sources, PENDING, open intent, unsettled obligation
   and unknown result. Stop/revoke the drain executor, prove no other authorized
   process can write, then release/expire the lease and invalidate old handles.
   Lease expiry alone is not the stop proof.
4. Make a consistent private snapshot of every quiescent database, including
   committed WAL state. Exact old exporter and independent raw read-only tools
   verify full history and the complete per-asset close. Produce a root and a
   provisional successor opening with no financial permission. Compare the
   original again immediately before retirement. Any change restarts review.
5. Obtain independent approval for that exact root, code/rules, migration
   executable, opening and certificate. Commit the narrow append-only terminal
   retirement operation on the original authority. Query actual durable outcome
   and old-binary refusals; do not infer success from a reply or process exit.
6. Consume the unique handoff certificate and CAS active epoch. Verify the
   registry's committed record, acquire a new successor lease, construct fresh
   services and verify the actual loaded artifact before intake reopens.
   Preserve the original as permanently read-only; old original-CID receipts
   remain queryable through the authenticated lineage.
7. Observe/reconcile the first real successor operation and original-CID retry
   through independent reads. Reopen intake only under its approved limits and
   permits. Any uncertainty halts the domain; approval does not waive a guard.

## If work stops or the reply is lost

| Last independently confirmed state | Required response | Prohibited shortcut |
| --- | --- | --- |
| Barrier not confirmed | Determine actual barrier and every in-flight permit outcome; do not export | Treating a halted account or stopped UI as a barrier |
| Quiescing, accepted CID unresolved | Query its original source and financial DB; finish old-runtime recovery | Drop PENDING, new CID, new shard or budget release |
| Export/prepared, old not retired | Keep candidate ungrantable; recheck old root. Abort candidate with an append-only result if needed | Starting candidate to test real writes |
| Preparation/retirement transaction failed before COMMIT | Confirm rollback and unchanged original metadata/financial root before retrying same ID | Manually deleting staged markers or claiming rollback from an exception alone |
| Retirement COMMIT unknown | Query tombstone/root using the narrow verified recovery reader; stop both writers | Reacquiring old lease because the command timed out |
| Original retired, registry CAS absent/unknown | Keep old retired; reconcile registry and continue the same exact approved handoff | Removing tombstone or preparing a different child |
| Registry active, successor lease absent | Reconstruct verified successor services and acquire a fresh permitted token | Rebinding old service objects or using old generation/PID |
| Successor financial COMMIT unknown | Query original CID and validate source/journal/receipt/terminal before retry | Guessing COMMIT failed or replaying against the old DB |
| New committed effects exist | Halt intake, reconcile all effects and advance through a reviewed new handoff | Pointer rewind, snapshot restore over the authority, or binary-only downgrade |
| Missing archive/runtime or corrupted snapshot/history | Preserve evidence and remain unavailable for writes; restore/reconcile through reviewed disaster recovery | Recomputing old IDs with new code or backfilling old decisions |

Before retirement, abort is reversible only by a recorded decision: revoke and
discard the ungrantable candidate, confirm no retirement/CAS, revalidate the old
root and exact original build, obtain a **fresh** old lease generation and new
service objects, and reopen intake last. An old process with its old token must
not resume. If any final old state changed after export, invalidate that root,
certificate and approvals. No immutable old business history is removed.

After retirement, rollback means a new forward epoch. Even if the successor
has no financial effects yet, activation/retirement are not erased. If it has
effects, first drain/reconcile it, take its actual complete close and bind the
next opening to that state. An older code artifact can be proposed only after
independent compatibility review of the current state/rules. A retired original
file never regains financial permission. Compensation, when required by a
business incident, is explicit new financial history with its own source and
approval; it is not deletion of a confirmed loan.

The model result file is `credit-authority-upgrade-model-result.json`. It is
bounded design evidence only. It cannot substitute for the actual-process,
actual-database, multi-runtime and independently approved goldens listed in the
protocol, and does not authorize an operator to modify an existing database.
