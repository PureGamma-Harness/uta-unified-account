# Actual process crash after COMMIT and original-CID recovery

The preregistered82d72fd case passed once on CPU3/Python3.12 at
2026-11-17 15:07:58.650011–15:08:19.916177 UTC (21.266s process, one unittest
21.107s). The wrapper ran a new isolated process group with a55s hard watchdog;
no watchdog fired. Exact hashes/commands/raw and selected child observations are
in `evidence/runs/credit-v2-process-recovery/attempt-01`.

The first real worker process constructed verified existing services, installed
the native capability, acquired a real15-second native lease, and committed
the original sourced loan0.4 and partial repayment0.1 through the actual FIFO.
It discarded both application replies and then called `os._exit(73)` without
releasing the lease. This is an actual disposable process exit, not a mocked
connection or successful callback. The private advisory checkpoint is not used
as proof of financial COMMIT: recovery independently queries the actual rows.

After actual lease expiry, a different real worker PID acquired generation2,
constructed new services on its real bound Database, queried both original CIDs,
and repeated their original canonical producer requests. Both returned their
original SUCCEEDED receipts; polling found no new work. Historical borrowing
replay and complete four-event journal verification passed. The entire selected
financial/source/terminal history was byte-for-value unchanged by recovery:
two sources, two intents, one decision, four journals, principal0.3, interest0,
customerBTC30000000 native units, poolBTC70000000 and clean foreign keys.
The replacement lease was released normally. Generic readiness remained false.

The native lease uses the real Linux CLOCK_BOOTTIME and boot/PID identity;
actual acquisition enforced expiry. The original run estimated its wait with
monotonic time on this host (10.265s), not an injected clock. The separate
financial/exchange provider in this process test remains the static synthetic
fixture. Actual UTC freshness is tested separately in
`credit-v2-realtime-freshness-checkpoint.md`.

The subsequent test-only correction estimates the wait with the same real
CLOCK_BOOTTIME as the native lease, avoiding assumptions about a host's earlier
suspend history. It changes no runtime or financial rule. The original passed
raw and its exact preregistered test hash remain unchanged; the corrected harness
will run in the final integrated matrix rather than repeat a21-second green
case solely for a one-line observer correction.

This proves the specific after-COMMIT/before-reply crash boundary and real
cross-process original-CID recovery. It does not establish a crash during
financial COMMIT, power loss durability, database corruption recovery, replica
election, multi-node RPO/RTO or production acceptance. No service/listener,
HMAC route, public enablement or real funds were used. The original code-bound
database was private outside Git and is retained for review; no writer lease,
token, auth or key rows are included in public evidence.

An older published V2 authority is pinned to its exact code/runtime; this case
does not provide a forward binary/schema upgrade protocol. Do not delete the
marker or rewrite history to force a downgrade. That protocol and the latest
baseline/ledger-catalog integration remain blockers before final acceptance.
