# Internal synthetic credit V2 milestone — Draft / overall NO-GO

This change adds a fresh-only, default-disabled internal synthetic USD8/BTC8
credit authority. Explicit sourced FIFO BORROW/REPAY commands close native
intent, actual financial postings, original receipts and terminal state under
one financial COMMIT. Borrowing retains a complete content-addressed dedicated
operation decision and archive-only replay. Generic trading readiness is false;
public/CLI new managed borrowing remains501. This draft is stacked on PR16 and
does not enable production or real funds.

## Behavior, persistence and compatibility

* The real installer validates complete original financial state, source claims,
  immutable offline global/shard allocation, exact schemas, loaded code and
  risk policy. Source+PENDING share a separate original producer COMMIT. Native
  context binds actual connection/Database/role/PID/thread/token and staged SQL.
* Explicit zero new interest/fee, Cross valuation, BTC borrowing and USD8/BTC8
  scales only. REPAY keeps the original interest-first four/seven-leg algorithm
  with market dependency NONE. Synthetic local actors are trusted internal
  test sources; HMAC PR18 remains separate and is not wired here.
* New immutable V2 marker, source/intent/expected-posting/allocation/config,
  dedicated code/policy/decision records and composite deferred obligations are
  installed atomically only on an unused unowned fresh guarded authority.
  PREPARED1 is never promoted. Complete installed V2 refuses actual old899/458
  ownership and oldad3 posting, with real old-source positive controls.
* Existing source constructors now have a verified existing-only read/control
  snapshot path. They run original full ledger/credit checks, exact compiled
  schema/configuration/audit checks and create no DDL/history/grant. A real new
  token-bound Database constructs new services; old objects are not rebound.
* Existing no-cap borrowing/repayment and original CID replay behavior remain.
  No automatic account migration, schema promotion or historical decision
  reconstruction is provided. A queue acknowledgement is not risk acceptance.

## Recorded runnable acceptance

| Evidence | Actual result and scope |
| --- | --- |
| `docs/credit-v2-first-actual-borrow.md` | Real fresh install/owner/source/FIFO loan0.4, four legs, decision/receipt/terminal, full reopen/replay and no duplicate CID; public501/readinessfalse |
| `docs/credit-v2-actual-capture-independent.md` | Independent Fraction oracle and direct original read-only SQL: gross assets/P/I/pool, original journal/hash chain/prehead/post rows close |
| `docs/credit-v2-first-followup-blockers.md` | Original partial-REPAY runtime red and observer harness error retained. Separate minimal native/harness fixes; only the two failed targets retested, both passed. Actual partial principal0.3 and halted/stale seven-leg repayment principal0.35/interest0/interestcash0.05 |
| `docs/credit-v2-repayment-independent.md` | Independent actual original-SQL four/seven-leg repayment validation; a forged balanced principal-first history still fails the independent interest-first rule |
| `docs/credit-v2-realtime-freshness-checkpoint.md` | New actual UTC provider/fresh native SID→loan/partial repayment→real five-second expiry/known503 no effect→different fresh SID recovery. Original static fixture clock is unchanged |
| `docs/credit-v2-actual-process-recovery.md` | Actual worker exits73 after both COMMITs before replies, real lease expires, different PID acquires generation2; original CID replay/query and full financial rows unchanged |
| Native history/late/legacy reports | Actual historical-candidate fix, caught late/context/DDL/obligation failures, full-capability old-binary refusal and same-process renewal/handover; original reds and narrow harness corrections remain |

These are bounded component/chain correctness runs. The original manual-state
fixture uses a fixed synthetic exchange clock; its three observed UTC values do
not prove live TTL. The separate real-UTC case proves only its stated freshness
path. The process case proves after-COMMIT reply loss, not mid-COMMIT power loss,
replication or multi-node RPO/RTO. No capacity threshold is accepted here.
Independent financial/SQL reviews sign their exact components, not production.

## Failure modes and rollback

Business refusal first rolls back the real SAVEPOINT and records only the
original-CID rejection. SQL/corrupt/late/unknown outcomes stay technical; query
the original CID before retry. Unknown heads do not release budgets or bypass
FIFO. Native final denial and actual staged-row checks remain fatal when a
caller catches an inner failure. No dynamic cross-shard limit recycling exists.

Before publication, failed installation rolls back DDL and ordinary binary
rollback is possible. After publication the authority is pinned to its exact
retained code/runtime. Recover with original CIDs and that compatible runtime;
never delete markers, downgrade formats, reassign unresolved claims or erase
confirmed loans. Forward code/schema upgrade of an already published V2 is not
implemented. New fixed-code fixtures do not repair older code-bound databases.

## Gates that block merge and production

* Exact stable91e4ae40 is whole-merged by96b9fdb; all368 previous M3 paths
  are byte-equal at that merge and23 necessary targeted checks passed. Root's
  independently accepted persistent-MAIN ledger-catalog baseline5a29611 is
  whole-merged byfbfbfea. Its original native-view interface red and minimal
  direct-checker alias060022c are retained; three new-source targeted controls
  passed. The raw unmanaged joined TEMP-shadow boundary remains separately
  open. A frozen final SHA, full supported Python matrix, CI and new package
  checks remain required; targeted checks do not replace those gates.
* Further crash/unknown/corruption/governance tests and complete independent
  acceptance; forward binary/schema upgrade remains unsupported.
* Normal new-order/matching/spot/withdrawal/mode-switch adapters, lending
  distress/liquidation, insurance/ADL and post-cap interest/pool changes are not
  enabled for V2. Opening supported exposures may be valued; new execution is
  not authorized by that valuation.
* HMAC first-source/revocation barriers, real currencies/custody, production
  financial approval, throughput/30-minute/stability/HA/DR gates remain open.

Public evidence is selected synthetic financial data, canonical code/policy
documents, source-only historical archives with LICENSE, and reproducible raw
results. Private original databases, auth/key/TLS material, runtime writer
nonces and signed URLs are excluded. The scoped tracked/current/history scan and
exact source-archive/test-marker allowlist are in
`evidence/publication/credit-v2-draft/`. Its one exact nonce-exclusion negative
test sentinel is classified only in two Python test/probe paths; no raw/JSON or
production credential exception is granted. This is a scoped publication check,
not a general security audit. The draft must remain unready and unmerged until
the remaining gates are met.
