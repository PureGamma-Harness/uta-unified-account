# Durable command inbox and terminal receipts

This opt-in protocol stores a command in the same local SQLite database as the
financial authority. `ack="durably_queued"`, `state="PENDING"` means that the
inbox transaction's WAL/FULL commit returned. It does **not** mean accepted by
risk, reserved, sent to matching, filled, replicated, or suitable for real funds.
Risk acceptance occurs later inside the fenced writer's financial transaction.

The initial supported kinds are `SUBMIT_ORDER` (existing limit-order policy),
`CANCEL_ORDER`, `PUBLISH_MARKET`, and privileged `SET_HALT`. Existing product,
account-mode, precision, reduce-only and liquidation-ID restrictions remain.
The follow-up `REPAY` command uses the existing credit service's same-connection
helper, including interest-before-principal accounting and journal verification.
Market and halt commands are internal operations requiring risk/admin authority
at the gateway. The queue library is an internal trusted boundary, not an API
authentication layer. Live deposits, new borrowing, account creation, fills,
matching requests, withdrawals, conditional orders and other client operations are
unsupported by this command protocol. Generic `enqueue(kind, command_id,
payload)` returns `unsupported_durable_command` (409) for unknown kinds and
never falls back to a synchronous service operation.

## API and storage

```python
queue = QueueStore(database, initialize=True)  # explicit offline first bootstrap
queue.enqueue_submit(account_id, command_id, order_id, symbol,
                     quantity, limit_price, reduce_only=False)
queue.enqueue_cancel(account_id, command_id, order_id)
queue.enqueue_market(command_id, snapshot)
queue.enqueue_halt(command_id, enabled)
queue.enqueue_repay(account_id, command_id, asset, amount)
queue.status(command_id, account_id=account_id)
queue.process_one(fenced_exchange, guard=router_transaction_guard,
                  credit=worker_credit_service)
```

Restart uses `QueueStore(database)` with `initialize=False`. Existing table,
column, index, integrity-trigger and policy checks fail closed. Partial schema
loss is never silently repaired. Bootstrap creates no account or funding and
does not enable managed mode. Enable the writer fence separately after offline
bootstrap; old financial writers must fail their database authorization check.

The financial database owns `uta_command_config` and `uta_command_inbox`.
Command IDs are globally unique within that database, not across independent
shards. A retry with the same kind, owner and canonical payload returns the
current durable record. Reusing an ID with different content returns
`idempotency_conflict` (409). Numeric strings and Decimals normalize exactly,
without ambient Decimal arithmetic. Payloads have strict fields and contain
the business order ID separately from the command ID.

The persisted monotonically increasing sequence orders financial commands for
each account. Pending market/halt commands form a separate bounded control lane
which is selected first; controls preserve their own sequence. This permits a
fresh quote to precede an older queued order, whose eventual risk decision
records current authoritative inputs. Account financial commands never overtake
an earlier pending command for that account, including during backoff. This is
not a global total execution order or a fairness/latency guarantee under an
unbounded control stream.

Ordinary pending capacity defaults to 1024 (range 1..65536), with an additional
16 shared cancel/repayment slots (0..4096). New ordinary commands are rejected
when the financial pending count reaches ordinary capacity; cancels and
repayments may use the extra slots.
Controls have separate capacity 4 (1..64). A full lane returns
`durable_queue_overloaded` (503) without inserting the new command. Existing-ID
queries/retries still work when full. Pending capacity includes backed-off
commands and is released by terminal states. It bounds admitted pending work,
not retained history, disk bytes, producer threads or SQLite lock wait. Terminal
history is retained; online pruning is unsupported.

Producer `inbox_transaction()` permits queue insertion, never financial writes
or terminal updates. Schema triggers also reject terminal-state insertion,
replacement of an existing identity, identity mutation, deletion, and changes
to terminal records. These checks apply even to direct producer SQL. SQL access
as the filesystem/database owner remains a trusted operational boundary.

## Execution and failure protocol

`process_one` checks that inbox and exchange use the same database and asserts
an enabled, valid writer token inside the transaction. No `RUNNING` claim is
committed separately. The worker selects an eligible pending account head,
validates persisted canonical content, opens a savepoint, runs the existing
service helper and writes its terminal receipt before the outer commit. Only
after that commit returns is the record returned to the caller. New order
acceptance also rechecks market freshness at the precommit checkpoint.

For routed operation the process runner holds the publication lock through the
entire transaction and supplies `guard(connection, command_record)` as a
context manager. It validates shard ownership, control generations, global halt,
publication barriers and market identity in the same transaction. The guard is
inside the command savepoint; failed business operations roll back guard writes
as well. Direct single-database operation requires the same valid managed fence.

| State | Meaning | Financial receipt |
| --- | --- | --- |
| PENDING | Durable intent, eligible now or waiting for retry/backoff | None |
| SUCCEEDED | Service transition and receipt committed together | Original result |
| REJECTED | Explicit, recognized business/market rejection; command writes rolled back | Stable error |
| QUARANTINED | Bounded technical retries exhausted; investigation required | Technical 503, no acceptance result |

An order command's original successful receipt remains stable even if a later
command cancels or fills that order. Query current orders separately for their
current state. A rejected command remains rejected even after collateral is
increased; use a new command ID for a new business attempt.

SQLite errors, ledger/storage failures, unknown service errors and programmer
exceptions are technical failures. They roll back the financial/receipt
transaction and raise `CommandExecutionError`, preserving `command_id`, sequence
and the exception cause. They are never serialized as a business rejection.
An exception after a real commit or a lost response leaves the outcome unknown
to the caller: query the original command ID before retrying or escalating.
Do not infer rejection merely because the worker returned an exception.

The explicit worker policy `record_failure(exchange, command_id,
max_attempts=3, backoff_seconds=0)` starts a new fenced transaction and first
checks durable terminal state. If the preceding response was lost after commit,
it returns that original terminal receipt without changing it. Only pending
commands accumulate technical attempts. The maximum is 1..100; backoff is finite
0..3600 seconds. The retry deadline uses the injected aware UTC clock and is
eligible when deadline equals now. Clock rollback may delay retry; it grants no
financial authority. Exhaustion writes `QUARANTINED` and releases the account
head. Operator investigation must precede any new-ID business resubmission.

Backoff permits other accounts to make progress. It does not let a same-account
cancel pass an unresolved earlier command: first resolve or technically
quarantine that command. This ordering rule is explicit; cancel reserved slots
are admission capacity, not a priority execution or immediate-cancel guarantee.
Unrecoverable storage failures cannot be promised a terminal record; stop or
back off the worker and retain/query the original ID after recovery.

Repayment remains available during trading halts and stale/missing market data,
using settled cash of the debt asset and the existing shared spot-lock policy.
The router guard must classify it as a risk-reducing operation. It remains behind
earlier pending commands for its account. The worker supplies its already
initialized `CreditService` bound to the identical exchange object; no nested
transaction or per-command service construction is used. Repayment and credit
command/journal identity use the inbox command ID, so the original receipt is
stable across restart and retry. An overpayment or insufficient cash is a
recognized business rejection; missing worker credit integration, corrupt debt,
SQL and unknown errors remain technical failures.

Repayment inputs use the bounded service amount contract: positive Decimal or
decimal string, magnitude at most 1e12 and at most eight fractional digits. The
producer also verifies exact integer minor units using the immutable configured
asset scale before acknowledging a new repayment. An unknown asset or invalid
precision is rejected before enqueue; this does not evaluate account debt,
cash availability or credit acceptance. No new lending is enabled by repayment.

## Deployment, recovery and rollback

1. Halt ingress and drain prior synchronous writers. Back up and verify the
   financial database. Bootstrap accounts/funding with authorized synthetic or
   approved data, initialize the inbox explicitly, and retain configuration.
2. Enable managed fencing and verify that the old service, old token and
   independently opened ordinary database cannot perform financial writes.
   Start only the token-bound process runner; grant producers metadata-only
   enqueue/query privileges.
3. Resume only supported ingress through durable commands. Publish fresh market
   and explicitly activate the relevant control generation. Independently verify
   actual matching, liquidation and settlement; queued order throughput is not
   matching-confirmed or settlement throughput.
4. After crash, reacquire a new valid fencing generation, reopen existing inbox
   without initialization, and query terminal receipts. Remaining pending work
   can execute again because business changes and terminal results share one
   transaction. Never reconstruct command history from an empty replacement DB.
5. For incident rollback, halt ingress, drain or preserve pending commands, stop
   workers and retain managed mode. Revert application code only to a release
   that honors the same fence and inbox schema. Returning to an unfenced old
   writer or deleting queue/history is unsupported. Restore from a verified
   snapshot/log procedure and reconcile every acknowledged ID before activation.

Run `python -m unittest discover -s tests -p 'test_durable_commands.py' -v` for
local protocol checks. Independent suites must exercise real process exits,
COMMIT errors, stale writers, poison isolation, matching/settlement, replay and
reconciliation. This delivery makes no multi-node replication, RPO-zero,
30-minute endurance, 10,000-per-second or production-enable claim.
