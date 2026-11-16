# Managed process soak tool

`benchmarks/run_managed_soak.py` is a new synthetic stability tool based on
`4c68f01`. It does not alter `run_soak.py` or the live 887/observer directories.
Read [the golden workload](managed-soak-golden.md) for independently calculated
fees, gross debt, account balances, matching and audit expectations. Earlier
887 results cannot qualify this different code, transport or authority.

The default is a 60-second smoke, at exactly 0.25 scheduled rounds/s with one
active round. A 10-second window schedules arrivals at 0, 4 and 8 seconds. There
is no catch-up burst; a delayed round delays the next actual start. This is a
paced golden scenario, **not an open-loop capacity benchmark**. HTTP requests,
queued acknowledgments, terminal account commands, matches, fills and rounds
are different counts. Six account commands commit in each round, together with
separate market/activation controls. Only the six committed account receipts
qualify as account command successes. Round latency starts at its originally
scheduled CLOCK_BOOTTIME arrival and includes CLI feed, HTTP, queue, matching,
checkpoint and recovery delay.

## Smoke and cold verification

Run from a clean checkout with OpenSSL available. Use a new private directory
outside Git, separate from every existing soak:

```sh
python benchmarks/run_managed_soak.py run --directory /private/new-managed-smoke \
  --duration 10 --worker-every 1 --parent-every 2
python benchmarks/run_managed_soak.py status --directory /private/new-managed-smoke
python benchmarks/run_managed_soak.py audit --directory /private/new-managed-smoke
```

The runtime creates private synthetic certificate/key/signing files beneath the
job's `private/` directory. It uses a seven-day loopback-IP certificate and random
HMAC secrets, all mode 0600, and a deployment-bound nonce store. The client uses
CERT_REQUIRED with IP verification. No private key/profile goes into Git or the
public evidence bundle. The real `uta.durable_cli serve` process creates its real
fenced workers with required decision audit. No development HTTP fallback or
invented fill is available. Public artifacts should include the non-secret
job/progress manifests, source hashes, checkpoint event exports and cold audit
output; exclude the complete `private/` directory and raw auth database.

Bootstrap runs in a separate process through the existing explicitly authorized
offline-before-seal contract. It uses public ShardRouter account, deposit,
market, credit limit, `fund_credit_pool(source_reference=...)` and borrow APIs.
A random job ID and synthetic funding proof are persisted before bootstrap.
The pool claim is recorded in the router's global registry and verified during
managed initialization and real worker startup. Borrowed principal is exactly
2 satoshi times planned rounds; no interest is generated. Bootstrap creates no
orders or fills and the managed initializer seals halted. Afterward the outer
runner writes only its checkpoint/logs and permitted control/auth metadata;
financial changes occur exclusively through the real worker.

Fresh feed publication is serialized before each round because managed publish
intentionally halts the barrier. Each full actual-UTC snapshot is checkpointed
before CLI publication, and a retry preserves its original version, bytes and
time. Existing original control receipts are queried before another activation
intent. Feed latency is included in round latency. A 30-second price-age policy
is not extended to hide a slow recovery. If the actual command becomes rejected,
quarantined or unresolved, the golden stream stops without a replacement CID.
CLI availability alone is not trading acceptance.

## Checkpoint and process recovery

The checkpoint database is distinct from the financial authority. There is no
cross-database atomic commit. Within the checkpoint database, each plan,
confirmation, round boundary and fault confirmation commits atomically with its
corresponding hash-chain event. A canonical method/target/account/payload/digest is
persisted before each signed POST. Every attempt queries the original account/CID
first. Only a scoped absent result permits resubmitting the same CID and bytes.
PENDING is only durable enqueue. After a financial COMMIT/checkpoint gap, a new
controller queries the original terminal receipt and records that fact locally.
An unknown step prevents every subsequent step and round.

```sh
python benchmarks/run_managed_soak.py resume --directory /private/new-managed-smoke
```

Resume preserves the original configuration, source, job ID, authority/auth and
checkpoint file identities. It stops only a recorded old CLI PID with its
matching start-time identity before starting another coordinator. Official orphan
recovery and PID-bound generation fencing run in the actual process router. A
historical partial-fill observation stays historical after its cancellation;
its checkpoint is not confused with the immutable admission receipt.

Configured faults send real SIGKILL to a recorded worker or CLI parent, verify
PID identity, and record a higher recovered generation. Timing just after POST
can fall on either side of COMMIT; it never proves rollback. A crash between the
signal and its checkpoint is explicitly unresolved until the original financial
CID and process generation are reconciled. A signal is counted only when this
controller actually sent it. The tool never signals 887/observer processes.

`STOP` in the job directory or SIGTERM to the runner requests a pause. Accepted
commands are queried within the bounded command budget; stopping does not release
or reject unknown financial effects. CLI shutdown drains HTTP before stopping
workers. A failed/incomplete initialization retains its bootstrap plan and files
for inspection; it is not automatically reinitialized or treated as a resumable
completed job. Do not delete authoritative files to make a smoke pass.

## Evidence and acceptance

The independent oracle uses integer minor units/rational parsing and raw
read-only SQLite snapshots; it does not call production fee, reserve, PnL,
portfolio or credit calculators to construct expectations. Every completed round
checks customer cash, fees, pool cash, gross principal, liability ownership, no
positions and no reserves. Final cold reopening checks 4 orders/4 fills/2 unique
matches/1 partial cancellation and 8 required risk decisions per round, six
terminal account commands, audit market/code/policy joins, immutable market
payload digests, per-currency journal conservation and posting projections.
Cancellation/repayment/new-credit decision-audit gaps remain explicit; this tool
does not invent missing risk records or qualify unimplemented products.

Append-only checkpoint events form a SHA-256 chain and export to bounded gzip
segments. The manifest records checksums and contiguous sequence ranges. Segment
files and manifest are fsynced/renamed separately from checkpoint commits;
recovery derives the export cursor from the verified manifest. Final auditing
requires every persisted event to be exported. `status` is only a read-only last
persisted observation. `audit` performs another cold read-only verification and
never extends the original elapsed-time qualification.

Source commit/bytes and the golden specification are recorded. Clean-source
checks run before process starts and round/control operations. Runtime writable
state and secrets belong outside the source tree. The operator must preserve the
frozen source; arbitrary OS-owner edits, same-path rollback of a complete old
backup, disk/AZ loss and replicated failover are not established here.

Both duration flags default false and require the actual completed final audit,
full planned workload, all exported logs, no unresolved step/fault, strict source,
one continuous controller session, and both real fault types exercised. Time is
measured using same-boot CLOCK_BOOTTIME; a boot change cannot manufacture elapsed
time. Controller resume preserves correctness evidence but cannot claim a
continuous 6/24-hour run. `production_approved` and
`capacity_10000_per_s_passed` always remain false.

## Preparing a future long job

No 6-hour or 24-hour job is started by this delivery. Runs longer than 60 seconds
require `--allow-long-run` and clean frozen source; dirty development cannot opt
into them. After reviewing the two smoke results and final source manifest,
reserve a separately reviewed resource window and a new directory. Defaults are
one worker kill each 30 rounds and one parent kill each 300 rounds. There are disk
budgets and one active round, not an unbounded in-memory workload queue.

A future approved command would specify the duration explicitly, for example
`--duration 21600 --allow-long-run`; 24 hours uses `86400`. This syntax is not a
launch approval. Do not reuse an earlier directory, alter a live source checkout,
reset debt/funding, or present the earlier 887 result as evidence for this tool.
