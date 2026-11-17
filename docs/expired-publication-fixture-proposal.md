# Candidate fixture/lifecycle repair: not yet executed

This proposal follows the preserved d421 failure, the single authorized original
observation and the integration lead's selection of a native kernel-lock
witness. It changes only `test_durable_faults.py`'s requested method, its
case-specific initialization parameter, and one test helper. All other existing
methods' ASTs are identical. Every `uta` runtime file is unchanged.

Only this fixture initializes with the real production-default **5-second**
lease from first acquisition. Other cases retain one second. The acquisition
event must actually contain exactly five seconds. No persisted expiry, clock,
token, quote time or production default is edited. A longer setup lease is not
a claim that a real one-second production lease may be revived or enlarged.

## Actual holder capture

The test selects its own shard0 child, opens its pidfd and records kernel birth,
boot and UID. It checks only that bound PID's `/proc/.../fdinfo` records for a
descriptor whose router-lock path, device and inode agree with the expected
private file. The full-file kernel record must be `FLOCK ADVISORY READ`, owned
by the selected PID. No worker function or native artifact is patched.

After pidfd SIGSTOP, the same binding must be in state T and retain the kernel
READ record. A separate actual nonblocking EX probe on that exact inode must
fail. If the read/stop race already released SH, only the same still-live,
unexpired original binding can be resumed for another observation. Setup has a
five-second horizon and at most eight captures. This does not retry a financial
command. The other shard is never paused solely to infer lock ownership.

Static peer review identified an additional necessary precondition: native SH
may already enclose a SQLite financial writer. After SIGSTOP, the candidate
therefore also requires a real `mode=rw`, timeout0 `BEGIN IMMEDIATE` followed by
ROLLBACK, with zero DML and unchanged connection total_changes. A busy writer
means that capture has not reached the intended pre-write phase. Only native
SQLITE_BUSY (including extended base5), or the exact builtin Python3.10
no-native-code `database is locked` form, permits resume/re-observation within
the existing eight-attempt/five-second capture budget. LOCKED, I/O, permission,
schema and other unknown errors fail. The probe installs no owner/UDF, does not
write data or change a lease, and is closed before the real durable enqueue.

An explicit unexpired-owner control waits .1 seconds while the owner holds SH.
It requires no pidfd exit, the same active generation and the retained kernel
lock. This guards against making recovery pass by killing a live unexpired
owner. Unknown or changed bindings do not authorize signals.

The original `held-gate-command` is enqueued once and must initially be only
durably queued/PENDING. One version2 snapshot is created and its original
bytes/digest retained. The stopped token is neither renewed nor modified. The
test waits for actual native remaining time <=.25 seconds, still active and
bound, then starts the original `publish_market(snapshot, timeout=5)` once.
The publisher's entry performs another genuine read-only bound/active check.
No timestamp is refreshed if this takes longer.

## Separate horizons

| Check | Budget and meaning |
| --- | --- |
| Native SH capture | Five-second setup horizon, max eight observations; not a financial retry or production SLO |
| Do not kill an unexpired owner | .1-second real pidfd wait plus actual active lease and retained kernel READ |
| Original bound owner exit | Within five seconds from original publication start, measured with pidfd |
| Persistent generation increase | Actual new active owner/generation observed within the same five-second recovery horizon |
| Original publication enters EX | Call-through observation of the parent's original lock, within that same five-second horizon |
| Whole publisher thread | Separate 15-second test watchdog for initial gate, receipt and final gate phases, each still using the original API timeout5 |
| External controlled experiment | At most 30 seconds including own-process cleanup; watchdog/incomplete evidence can never be PASS |

The 15-second thread watchdog is not a replacement for any five-second recovery
assertion and is not a proof of the API's hard end-to-end latency: SQL/OS work
also occurs inside its phases. Both SIGSTOP/capture timestamps and publication
timestamps are recorded, so lease-wait time is not hidden in a faster RTO claim.
If recovery fails, any forced own-child cleanup is explicitly marked and
cannot make the earlier failed assertion pass.

## Financial and source checks

Both original per-shard publication CIDs must return their exact persisted
SUCCEEDED receipts and the exact original local snapshot bytes. The test never
creates a replacement publication or order ID. It retains orders<=1 and adds
ORDER_ACCEPTED events<=1, the original account/order identity, unchanged ledger
events/postings/balances, liabilities, fills, positions and matches. Native
trading/ledger schema rows and configured cache sizes must remain unchanged.
This is direct row and receipt reconciliation for this small fixture; it is
not an independent full risk-model replay or an HA/RPO proof. A PENDING business
order is not counted as an admission merely because publication completed.

The candidate recorder also captures the fixture's own phase observations and
matches the historical original assertion explicitly. It no longer interprets
any earlier testcase failure as reproduction of the original line1252. The
original baseline recorder/result remain immutable in their earlier archive.

Only syntax compilation and AST/runtime-delta checks have run for this code.
There has been **no candidate native run**, controlled red/green, whole suite,
capacity test or production approval. Static peer review and explicit controlled
run authorization are required before executing it.
