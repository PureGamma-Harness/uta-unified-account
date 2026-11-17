# Independent static review of spawn-registration recovery

Reviewed candidate b689b42455c458c63677ca7e30a9aa3ea53bb047, parent
 e4396b4b1fd9c2e3a138e48a045feffe158705cc. Status: **static NO_GO pending the
lifecycle findings below and separate verification**. No tests, SQL, service,
native fault, source mutation, timeout change or old-job action was performed.
The author's untracked future tests were not executed or accepted as evidence.

The candidate changes only uta/durable_process.py (+121/-11). Storage, the
original0.6s/4s testcase and its assertions are unchanged. Selected original
functions—including _run_worker, registry insertion, orphan recovery,
publish_market, set_kill_switch and close—have identical ASTs. This preserves the
original TTL/API timeout and storage FULL/busy-timeout policy; it does not prove
that the four-second operation now completes.

The original PR22 result remains run44162304965 attempt1, Python3.11.18,
1801/0FAIL/1ERROR. The first-EX router_busy traceback and adjacent supervisor
locking-protocol traceback remain preserved in evidence commits b06d0b5/349223b.
Their timing/causal ambiguity is not resolved by this candidate. A plausible
recovery change is not a reproduction, accepted fix, new CI pass or release gate.

## Findings sent to the author and integration owner before this report

B1 — Unknown-cleanup barrier can be bypassed across close/start. The new
_spawn_blocked set is checked in the monitor loop (1292/1299), but neither
start's unconditional _spawn call at1279–1280 nor _spawn itself respects an
existing block. close at1604–1614 swaps out workers, attempts stop/join/kill/join,
and closes handles without checking a final post-kill alive outcome. It does not
establish a successful cleanup receipt or clear the old block on that basis.
A subsequent start on the same router can therefore create a new PID/nonce;
a successful new registration discards the block at1164. This contradicts the
stated rule that unknown cleanup must prevent a new spawn until confirmed.
Keep the barrier tied to actual cleanup confirmation across lifecycle entrypoints.
This is a static contract counterexample, not a claim of observed financial
double writing: the originally failed child had not received its start gate.

B2 — References are dropped before resource cleanup is complete. On confirmed
child exit, _spawn pops _workers and _start_gates at1142–1145, then attempts the
handle closes and process.close at1146–1155. Any of those closes can fail, producing
cleanup_complete=false and a blocked shard, after the router's recovery inventory
has already lost those references. Its later close cannot retry those resources;
transient exception/GC reachability is not an owned cleanup inventory. Preserve
resource ownership until completion or retain an explicit incomplete-cleanup
record containing the necessary handles. Because child exit was checked first,
this finding alone does not imply an active second financial writer.

B3 — The new retry path can spawn after shutdown is requested. The monitor's
outer stop.wait at1289 can return before it blocks on _mutex. While it waits,
close may set _stop and wait for the monitor. When the mutex becomes available,
the new retry_at loop at1291–1296 can still call _spawn and release a new child
because it never rechecks stop. The existing dead-worker path at1320 explicitly
requires not self._stop.is_set(). Apply the same lifecycle rule to retries so
shutdown does not introduce a new actor or extend cleanup with fresh startup.
This is an unexecuted source interleaving, not asserted as the original CI cause.

## Positive financial/recovery properties and their assumptions

Within the intended _record_process failure path, the new child gate has not
been released. _run_worker still checks that gate and its stop signal before
financial initialization or acquiring a writer token. The handler signals stop,
joins and, if needed, kills its own unreaped multiprocessing child; a retryable
classification is used only after cleanup_complete. Native BUSY/LOCKED/PROTOCOL
and exact legacy strings are distinguished from other OperationalError values.
Unknown errors are blocked rather than reclassified as financial health.

The handler does not repeat the uncertain registry INSERT, rewrite its nonce,
delete a possible committed audit row or invent a NOT_COMMITTED result. A lost
reply after COMMIT remains UNKNOWN; a later attempt uses a new child and nonce.
Registry immutability, gate-before-authority ordering and old-orphan reconciliation
are unchanged. This is sound direction under the existing trusted-parent,
unreaped-owned-child assumptions, subject to the cleanup barrier findings above.
No actual after-COMMIT reply loss or resource-failure case was exercised here.

## Retry, isolation and API boundaries

The backoff interval is capped at1s, but there is no finite attempt/horizon budget.
The counter saturates and retryable failures can continue spawning indefinitely.
If indefinite bounded-rate recovery is intended, document that policy and
escalation/capacity limits; do not describe it as a finite number of attempts.
Registration plus up to1.1s of gated-child cleanup still runs under the shared
parent mutex. Per-shard catches preserve flow only after the synchronous call
returns; they do not by themselves establish fair monitoring latency for other
shards during an original control-database timeout. These are unmeasured coverage
and policy limits, not demonstrated new causes of the old CI error.

Only _SpawnRegistrationFailure is caught around the spawn sites. Other preexisting
pipe/process/cleanup failures can still terminate the monitor; the new diagnostics
can fail closed when the monitor is gone, but this patch is not universal
supervisor exception isolation. Allocation and process-start failures outside or
before full child ownership also require explicit coverage if included in scope.

supervisor_alive and per-worker last_spawn_failure are additive router diagnostic
fields. The latter contains fixed codes, PID/count/boolean state and bounded
SQLite errorcode, without nonce or exception message. financial_ready now requires
a live supervisor, so actual router readiness degrades rather than silently
remaining true after that thread dies. These observations remain diagnostics,
never an individual financial authorization.

ProcessBackend.diagnostics currently filters out both new detail fields. Public
managed-gateway clients receive the tightened ready/financial_ready and reason,
but cannot inspect supervisor_alive or last_spawn_failure there. Clarify whether
the new details are router/CLI-only or extend the reviewed operations API. Also
state that last_spawn_failure.recovered means a newer registration was confirmed;
it is set before the child has reported real READY and is not financial recovery.

## Evidence, next gates and rollback

The small sparse review branch contains only this report, the immutable candidate
diff, source/AST hash index and static findings. It changes no implementation and
retains no private DB/key/TLS content. The next candidate must close or explicitly
resolve B1–B3, then pass independently reviewed controlled after-COMMIT unknown,
cleanup failure and shutdown/retry cases, followed by the complete exact-source
matrix. No new SQL/native experiment is authorized by this report. The author's
separate driver/tests plan remains subject to root GO.

Rollback of this review itself is exclusion of the evidence-only commit while
preserving original CI artifacts. No production deployment or source rollback
was performed. Overall production and the original failed CI gate remain NO_GO.
