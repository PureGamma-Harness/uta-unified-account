# Managed initialization without a historical-replay writer lock

Status: implementation-risk review, not an approved or implemented optimization.
Base source: `28493d4`. Reviewed evidence: recovery-scaling `ae0f88f`, including
its original analysis and per-phase observations. No runtime or stored authority
has been changed by this review. Capacity, HA and production gates remain false.

## What the evidence establishes

The synthetic history contains balanced system journal events and two unfunded
customers, not exchange matched-trade history. At 200,000 events, full ledger
replay occupied 4.847354 seconds and acquire-to-renew used 4.911099 seconds of
the ordinary five-second lease. At 250,000 events the first generation was
observed alive after its persisted expiry and then replaced. Generation two
completed replay in 4.717773 seconds and sent READY during close, after the
six-second observation window. This establishes a startup-expiry incident and
duplicate work, not permanent failure or a perpetual respawn loop.

`ExchangeService.__init__` currently calls `DurableLedger.verify` inside its
final `database.transaction()` (`BEGIN IMMEDIATE`). A renewal thread alone
cannot solve this: renew needs the same SQLite writer lock. Raising the TTL or
skipping replay does not remove the underlying dependency.

Other potentially large initialization work includes `CreditService._verify`,
the worker's all-account shard check, global funding claim collection and shard
funding reconciliation. These must not silently be treated as constant time.
Matcher/scheduler setup and guard installation are additional write phases.

## Protocol comparison

| Candidate | Binding needed | Main risk / complexity |
| --- | --- | --- |
| Pre-acquisition read verification, then compare ledger head | Insufficient | Balance projections, debt, orders, schema or guards can change without changing the head. |
| Pre-acquisition read verification, then recompute every projection digest | Complete data scan in the acquired lease | Moves another history-sized operation into the same expiry constraint. |
| Pre-acquisition verification under router EX gate | Continuous gate plus proof that every writer and acquire participates | Direct `Database.for_writer(...).transaction()` and `WriterFence.acquire()` do not require that gate. The current API cannot claim this exclusion. |
| Owned read-only verification with separate lease heartbeat | Continuous current token, no financial actor in the owning process, immutable authority identity and fresh final fence/guard check | Small existing-only read phases and a bounded renewal lifecycle; no reusable verification cache. Preferred for independent review. |

`PRAGMA data_version` values from different connections, inode/mtime alone,
ledger head equality or a caller-supplied `verified=True` are not acceptable
substitutes for those bindings.

## Proposed minimum owned protocol

The optimized entry is the managed spawned-worker initialization pipeline only.
The ordinary public `ExchangeService` constructor retains its original complete
write-transaction verification path. No user profile, HTTP request or generic
configuration file can supply a verification result or skip flag.

1. The existing supervisor completes registered-owner recovery. The child
   acquires its actual PID-bound token through `WriterFence.acquire`, preserving
   its current generation, boot and expiry rules. Acquire's writer transaction
   serializes after any prior writer transaction. An expired old owner cannot
   commit using that generation because the transaction-end fence check remains.
2. Before any initialized service object is published or any queue/background
   consumer starts, enter a private initialization scope for this canonical
   authority, token, inode and initializing thread. Only this thread may perform
   financial initialization writes. A proposed small process-local registry in
   the existing financial transaction guard rejects financial transactions from
   other threads while the scope exists. Fence-control heartbeat writes and
   producer-only inbox INSERTs retain their existing restricted roles.
   A short fenced writer barrier after registration drains any same-process
   transaction that entered before registration. Only then may read verification
   begin. Registration alone would leave an already-open writer interleaving.
3. Start a bounded keeper immediately, before process-registry work or service
   construction. It uses a separate connection and only `WriterFence.renew`
   for the exact acquired token; a separate token is never acquired. Anchor
   renewal to the start of the actual renewal attempt, not initialization end.
   Its SQLite wait is bounded below the lease budget. Any renewal exception,
   including a COMMIT outcome unknown to the caller, irrevocably poisons this
   initialization attempt. It is not washed into success by querying afterward.
4. Short, ordinary fenced writer transactions validate/create permitted runtime
   schemas. They retain current persistent guard installation and COMMIT checks.
   Long existing-state verification then uses existing-only `read_transaction`:
   exact reference ledger replay; credit receipt/debt verification; shard account
   and funding reconciliation. The same actual verifiers run, with no cached
   pass result. No financial commands run between these phases. Producer inbox
   arrivals may commit but cannot change the verified financial projections.
5. A private scope can attest only a verification it actually executed for the
   same in-memory service/ledger object. It is thread-, authority-, token- and
   attempt-bound, single-use and not serializable. A forged, expired, reused or
   mismatched scope is rejected. This is lifecycle coordination, not financial
   authorization: the SQL writer fence remains authoritative for every mutation.
6. Close all read verification transactions before final binding. A long read
   snapshot contains the **old** lease row even when the keeper has renewed it;
   checking expiry on that snapshot can falsely reject a healthy owner. Open a
   new short financial transaction, validate the exact current schema/guard
   manifest and authority identity, check that the file inode is unchanged,
   assert the current PID/boot/generation/live lease, and check that the keeper
   and initialization deadline have not failed. COMMIT must successfully return.
7. Stop/join the initialization keeper without a dangling renewal and hand its
   last actual renewal timing to the normal loop. The loop must not schedule the
   next renewal from the end of slow verification. Only after successful final
   binding may the child send owner READY and publish the service objects. READY
   is still ownership readiness, not market freshness or financial readiness.

The continuity argument comes from the current generation and private actor
exclusion, not an unchanged ledger head. Another process cannot present this
PID-bound token; acquiring a new generation requires expiry, after which final
binding fails. In-process callers cannot mutate during the private startup scope
through supported guarded financial transactions. Code executing arbitrary
Python or privileged raw filesystem/database mutation is not an untrusted client
boundary; the application cannot defend itself against an actor replacing its
own guard functions. Existing private-file/inode and persistent SQL protections
must nevertheless remain intact.

## Required interleavings and failure outcomes

| Interleaving / fault | Required outcome |
| --- | --- |
| Old financial transaction began before acquire | Acquire waits on its writer lock; it either commits under its still-valid old fence or rolls back before new acquire. |
| Another owner tries acquire during healthy read replay | Existing live lease returns `lease_busy`; it cannot write the financial state. |
| Keeper pauses, storage stalls, or lease expires | Attempt is poisoned; no renewal revives an expired generation, no READY. Existing supervisor can replace the process. |
| Replacement acquires while verifier still holds its old RO snapshot | Old verifier may finish computation but new final transaction rejects its stale token. |
| Another thread reuses a valid token in the initializer process | Private financial-role registry rejects it; tests must not merely assume token secrecy. |
| Producer submits/retries during replay | Only canonical PENDING inbox rows can be added. No pre-reserve or terminal financial receipt is invented. |
| Old event, posting or materialized balance is corrupt | The same complete reference replay rejects; keeper is stopped; no READY or acceptance. |
| Credit debt/receipt or shard funding is corrupt | Existing corresponding verifier rejects; it must not be bypassed by ledger success. |
| Required guard definition or protected table changes | Existing exact guard inventory verification rejects, without repairing it. |
| Canonical authority file is replaced between phases | Inode/identity binding rejects; do not accept matching sizes or matching ledger heads. |
| Short initialization COMMIT fails or response is lost | Attempt does not claim binding/READY; discard private scope and stop keeper. Reopen follows existing idempotent schema/fence recovery. |
| Stop, parent death or bounded initialization deadline | Stop renewing, do not publish objects or READY; abort the private scope. Existing process lifecycle eventually terminates an unresponsive verifier. |
| Cold restart | Full reference verification again. No durable verification receipt or cross-generation cache is consumed. |

The keeper needs an explicit finite initialization deadline independent of TTL,
plus stop/parent-death checks. Otherwise a stuck verifier could renew forever
without being ready. For the first implementation, deadline selection must be
an explicit bounded startup policy, not an automatic TTL enlargement. The
deadline is a fail-closed work budget; it is not a measured universal RTO.

## Minimal code boundaries proposed for review

- A private initialization context/keeper module, without a public skip flag or
  persisted success record.
- A small financial-role scope check in `writer_fence` transaction setup; it
  must not weaken managed validation or give the keeper financial privileges.
- Managed-only internal verification context hooks in service and credit startup
  to split schema writes from existing complete RO verification. Public defaults
  keep the reference behavior.
- Worker-view reconciliation uses a read transaction; it is already SELECT-only.
  `_run_worker` owns the keeper from actual acquire through the final fresh
  binding and transfers renewal scheduling to the main loop.

No market/risk formula, ledger algorithm, schema version, token format or old
binary is changed. Any internal hook must reject invalid contexts rather than
falling back to an unverified path. Matcher/index initialization that still takes
too long must fail its lease/deadline; a later separately reviewed schema
preparation protocol can address that dimension. A first fix must not claim
unbounded startup scaling for every possible product/history shape.

## Independent review and acceptance before runtime merge

Use small deterministic fixtures and a deliberately paused real verifier to
prove multiple actual renewals can commit while the verifier's RO transaction is
open. That distinguishes the protocol from a renewal thread blocked behind
`BEGIN IMMEDIATE`. Cover current-token and stale-token financial writers,
same-process competing threads, continuous producer arrivals, every corruption
class above, real COMMIT failure/unknown outcome, stop/deadline/parent death,
recovery with the original command ID, and keeper thread cleanup. Verify that
public constructor behavior and reference numerical outcomes do not change.

First tests must run on one CPU with small histories. No 50k+ cohort or prolonged
run is authorized by this review. After independent correctness review, request
a coordinated same-source scaling experiment with original artifacts retained.
The 250k result is motivation, not performance evidence for a future patch.
