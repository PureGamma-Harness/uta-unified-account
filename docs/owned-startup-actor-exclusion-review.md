# Owned startup: actor exclusion is not yet a sufficient financial certificate

Decision: **phase2 NO_GO**. Phase1 only records typed observations and changes
no admission. This review enumerates the actual startup call graph and its
write domains, but cannot prove that a fresh same-token lease alone certifies
every previously verified financial snapshot. No SQL or native experiment was
performed. References below use unchanged business source9b4fcf5/base6010;
phase1 CODE6303ed4 adds telemetry without altering these SQL/decision paths.

## Full stock startup sequence and domains

| Stage | Source entry | Reads/writes and attestation boundary |
| --- | --- | --- |
| Acquire | durable_process._run_worker:471–483; WriterFence.acquire | Same-PID generation/lease acquired inside child; no READY or financial verification receipt |
| Owned enter | startup.__enter__:194–219 | Register path/inode scope, start restricted keeper, drain earlier financial writers with a fenced no-op version write |
| Process registry | durable_process:488 | OWNED registration in router control DB; this is a separate authority, not a shard-financial snapshot |
| Bind/reconcile | sharding.ShardWorkerView:749–765 | Bound shard identity; router lock and global funding claims; shard reconciliation in RO; rejects inconsistent claims |
| Exchange foundation | service:177–189; DurableLedger.__init__:301–340 | Claim compatible authority; ledger tables/assets/version checks; fixed trading/credit/matcher/schedule schema preparation before full ledger replay |
| Prepared worker | startup.prepare_schema:266–281; supervisor.ExchangeWorker:23–47 | Matcher and scheduler metadata construction; Event/RLock/cache objects; no worker start/matching/settlement |
| Full ledger | startup.verify_ledger:304–319 | One RO snapshot verifies original complete ledger and records full schema inventory; entry lease assertion is the observed error site |
| Post-ledger policy/audit | service:190–218; decision_audit.install | Matching-policy/config INSERT OR IGNORE and audit installation/market/code-policy metadata; these are real writes after ledger verification, not a globally read-only interval |
| Credit | credit.__init__:52–66; startup.verify_credit:326–337 | RO _verify checks gross debt projections, limits, original commands and pool balances; it is not another full journal replay |
| Transfer prepared worker | startup.take_worker:283–302; sharding:777–779 | Exact object/config/state checks; worker remains not started |
| Managed spot | durable_process:495–500, _verify_managed_spot_source | Another guarded RO read and existing-only spot construction; analogous snapshot-entry binding must be considered separately |
| Optional batch history | durable_batches.__init__:100–106; durable_process:501–507 | RO schema, actual writer assertion, all immutable manifests/member outcomes; concurrent producer INSERTs are a separate queue visibility domain |
| Final owned bind | startup.finish:339–357 | Require complete verifier flags/object identities; stop keeper, fresh ordinary same-token renewal, current schema/no-op financial COMMIT, mark finished |
| READY | durable_process:510–525 | Nonbatch sends lifecycle READY within owned scope. Batch exits scope, query-all recovers unresolved attempts, renews the actual token, then sends READY. This intentionally advances receipt metadata after the earlier history read. |

This sequence does not invoke the background worker before READY. It is a
source-order fact, not a bounded OS scheduling or five-second recovery proof.
READY delivery after arbitrary delay is not a current-lease capability; later
financial operations still require their original fresh native fence checks.

## Which actors are excluded, and which are not

| Actor or path | Source enforcement | Code conclusion / residual obligation |
| --- | --- | --- |
| Same PID, another thread, financial role | _initialization_write_gate._require before SQL and _assert_initialization_actor after BEGIN | Excluded while the registered authority matches; actual lock/fence execution is not rerun here |
| A transaction started before registration | Owned-enter BEGIN IMMEDIATE/no-op drain plus persistent fencing | Drained before constructor replay under the cooperative Database protocol |
| Another PID/old generation | _assert_token PID/nonce/generation/boot plus native DML and final-COMMIT checks | Cannot use the current token through official wrappers; trusted OS/file owner remains outside this application boundary |
| Alias/replacement path | Active path/inode registry, private regular-file checks and _BoundShardDatabase identity checks | Alias/replacement is not a silent authorization transfer; failure still blocks startup |
| Keeper/control role | _initialization_write_gate and control authorizer restricted to fence objects | Lease writes are permitted; they change the lease row hidden by older RO snapshots, not financial replay data |
| Producer/inbox role | Inbox-only INSERT policy and immutable original identities | New PENDING commands can arrive; no assumption that the whole DB stays byte-identical. Existing member identity/state stability needs its explicit guard dependencies. |
| Batch metadata role | Active actor check after BEGIN; only batch-table INSERTs | Not a blanket no-write interval; recovery metadata must be linked to later READY state |
| **Owner thread with bound financial DB** | _require intentionally accepts this exact thread/token | **Not excluded**. All ordinary fenced financial transactions remain callable, including during the owned scope. No automatic dirtying of _ledger_verified/_credit occurs after arbitrary owner-thread DML. |

The distinction is constructive: after full ledger/credit verification, the
private owner API still permits a bound financial transaction before finish.
Mutable projections such as ledger_balances are not the immutable journal
tables. The generic fence verifies ownership and protection definitions; it
does not rerun full financial replay on every such write. finish checks schema
and current ownership, not a complete financial-data watermark. This is a
source-admissible proof gap in a general owned-context certificate, **not** an
executed stale-success test or a finding that the fixed worker factory actually
took this sequence in either original CI error.

## Dependencies that cannot be collapsed into a current lease/head

- Ledger proof covers schema/assets, events, postings and balances. One MAX
  event sequence does not alone bind every mutable projection or scale/config.
- Credit proof covers liabilities, debt ledger accounts, limits, pool funding
  commands/results and pool balances. Credit._verify does not repeat full
  DurableLedger.verify; cached ledger_verified is not a new data certificate.
- Trading/decision-audit config and metadata can be installed after the ledger
  RO read. Their allowed changes and relevant policy versions need explicit
  domain mapping rather than a claim that all later operations are reads.
- Managed spot and batch-history verification use additional snapshots. Batch
  member identities/outcomes and the producer inbox have distinct change rules.
  Batch recovery after scope exit intentionally creates validated outcomes;
  this requires a stage-linked proof, not a universal unchanged-DB assertion.
- Router funding claims and shard receipts live in different authorities. The
  router lock/reconciliation contract is relevant; a fresh shard token alone
  does not establish a cross-DB logical-time certificate.
- Database subclasses and supplied clocks/callbacks are Python extension
  points. The stock _BoundShardDatabase hook checks shard identity, but a proof
  for all allowed owned contexts cannot silently assume arbitrary owner-thread
  callbacks never write. Actual factory purity restrictions must be stated and
  independently verified before adopting that narrower theorem.

Supervisor NORMAL-cache dependency hashing is a separate risk scheduling
mechanism. Neither that cache nor an old ledger head is accepted here as a full
startup financial certificate. No new field with such authority is introduced.

## Remaining proof gates

An admission-changing phase must either bind a sufficient composite financial
watermark at each verified domain and enforce all writer updates, or prove the
exact permitted factory/callback graph excludes every relevant change through
the final fresh COMMIT. Both require implementation details, not a declaration
that actor exclusion exists. Any watermark advancement needs a validated new
stage or full resnapshot/reverification policy; it cannot be ignored, guessed,
silently cached or combined with a different current generation.

No such complete proof is available in this delivery. Consequently there is
no phase2 runtime patch, relaxed snapshot-expiry condition or new READY route.
Original0.4s fixtures, keeper interval,60s work deadline and expired-renewal
refusal stay unchanged. Phase1 overhead spans all read TransactionGuards and
requires later measurement; no timing/performance equivalence is claimed.

## Delivery and rollback

This review adds only a source-bound proof assessment. It grants no native,
financial, capacity or production approval. Revert the new review files to
remove it; preserve all first errors, baseline RED and later telemetry/code
review history. Any future admission behavior requires its own data migration,
deployment, recovery and rollback acceptance.
