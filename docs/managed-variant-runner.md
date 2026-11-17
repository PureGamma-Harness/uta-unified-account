# Short managed variant runner

`tools/run_managed_variants.py` is an external, standard-library orchestrator.
Its default mode prints a preparation record after reading the unchanged base
plan. It opens no SQL store, starts no child, creates no output directory and
does not change affinity. It imports no trading, risk, ledger or SQLite module.
It does not authorize execution or assert that source qualification passed.

```sh
python tools/run_managed_variants.py --source /path/to/candidate
```

The separate [registration template](../benchmarks/plans/20261117-managed-variants-execution-template.json)
deliberately has `execution_go=false`, a zero placeholder source SHA and empty
qualification arrays. It cannot run a case. Do not modify the original base
plan or historical red results. Fill a **new** registration only after the new
release source, CI, package and coordinated compute-window gates pass.

## Exact-source execution gate

Execution requires `--execute --registration /private/registration.json`.
The registration, base plan and source must agree; the runner must itself be
part of that exact clean source. Every tracked source byte is hashed before
and after every case. A source/registration change, failed or unknown proof,
unavailable CPU, stale cohost or insufficient reservation refuses/halts work.
There is no override, same-runtime exception or legacy qualification transfer.
In particular, the failed a35 CI jobs and old 763/a35 results cannot qualify
the new runner/helper source.

Qualification uses hash-pinned original records, not a single approval flag:

- Three full local `tools/run_validation.py` runs, Python3.10/3.12/3.13, at the
  exact candidate SHA. Summary, worker JSON and full log must agree on the
  registered suite count, zero failures/errors/skips/expected failures, clean
  unchanged source maps and actual exit0. Resource/unraisable warnings fail.
- Eight completed successful CI records, push and pull_request for each of
  Python3.10/3.11/3.12/3.13. Raw run/job JSON must bind the candidate head SHA,
  repository, event, run/job and matrix interpreter. Every full validation
  input hash must match the new source. A PR merge identifier may differ from
  the head identifier; exact input maps and the raw run head bind it to the
  candidate. Push summaries must use the exact candidate SHA.
- Fresh package verdict, full tracked/archive manifest, installed8+console8,
  installed read-view3 and actual runtime/each-tracked-ZIP omission records.
  All package records bind the exact SHA and same artifacts/runtime map.
  Historical failures inside retained ZIPs stay historical failures.

Each reference has exactly `path` and `sha256`. Qualification JSON is read
from regular files with NOFOLLOW, bounded size and duplicate-key rejection.
Log bytes are pinned too. CI provenance collection and the integration owner's
registration remain the trust boundary: this offline checker does not sign
GitHub responses or claim independent provider authentication. Preserve the
original collected provider records for review; do not manufacture them from
an expected status. Synthetic positive qualification fixtures in tests are
contract tests, never release qualification evidence.

## Cases, metrics and stops

All arms have durable capability True. A is batch0/cache0; B3/B8 change only
batch size, C8/C100 change only cache capacity. Each comparison runs AB/BA/AB
with a fresh path/authority and cold cache: 24 cases, 200 original arrivals per
case, 20/s for ten seconds, 100 accounts, two shards and the base plan's guards,
audit, controls, feed, queues and drain. CLI arguments are constructed from a
typed case; arbitrary command or limit overrides are not accepted.

Exit0 alone is insufficient. The runner independently checks raw unique IDs,
schedule, receipt chronology, OPEN/unfilled reserves, counts, rejection mix,
all/success/ACK N/max/exact nearest-rank quantiles, histogram upper bounds,
actual router/spawn settings, PIDs/fences and reported RO capability/audit/
version/ledger reconciliation. It checks all-CID technical facts and requires
both `probe_qualification.passed` **and**
`financial_soft_deadline_passed`. A late-success case retains its derived
metrics and stops the next case, even if the benchmark CLI returned zero.
Malformed data, lost results and failed reconciliation remain failed/UNKNOWN
evidence; no retry replaces the original case or financial IDs.

This JSON checker does not itself reopen financial SQL: the child's original
post-shutdown RO reconciliation, receipts and manifests are retained. The
post-COMMIT financial receipt denominator includes observation/drain, excludes
setup/close, and is rebuilt from the new actual timing footer below.
Enqueue ACK, business rejection, selection membership, execution membership,
unique financial success and physical COMMIT are different measures. Native
cache hit counters and physical COMMIT counts remain **unmeasured**.

These are unsaturated local SDK admission diagnostics. They include global
publication/HALT costs and changing rejection mixes; a higher success count
alone is not a risk-kernel speedup. They provide no fills, matching/liquidation,
REST/TLS ingress, replication, 10,000/s capacity or production qualification.

## Resource and process ownership boundary

Register two explicit allowed CPU IDs (proposed2,3), plus every cohost PID,
birth tick, immutable source and JSON heartbeat pointer. The original4471 and
8784 must be registered/protected. Cohost inspection uses JSON and `/proc`
only. No signal, DB access, status command or source edit targets a cohost.
The JSON must also expose an empty alerts list and the underlying work's
heartbeat age at observation. Current observation age is added to that work
age; a fresh observer timestamp cannot mask a stale or unhealthy producer.
Missing fields require an explicitly reviewed read-only cohost JSON adapter,
not a default healthy value or a changed timestamp.
The parent/launcher/child bind the chosen CPU set and the child's actual kernel
affinity is recorded. Affinity is not cpuset or dedicated-host isolation.

Each case starts a new session. The external watcher records the actual
leader PID, `/proc` birth/session/group and pidfd. It detects exit with pidfd
while keeping the leader unreaped, preventing PID/PGID reuse through cleanup.
Only its own verified session can receive TERM, then KILL after bounded grace;
the leader is explicitly reaped and no live group members may remain. Live
descendants after a leader's unexpected exit also make the case UNKNOWN.
No preexisting process is adopted or killed. Owned process/stream evidence
persists separately from financial results. The failure model assumes a
scheduled, living watcher/kernel; watcher death or uninterruptible kernel I/O
cannot be turned into an asserted wall-time guarantee. Incomplete cleanup
stops work and requires investigation using the retained owner identity.

Both stream capture and output growth have caps. Normal stdout/stderr are
preserved byte-for-byte with hashes. On output overrun only a bounded prefix
can be retained; it is explicitly marked incomplete/UNKNOWN, never passed as
a complete original log. Financial authorities are never deleted or reset.
Resource checks poll during a case: filesystem growth can overshoot between
polls, so cleanup headroom is reserved; this is not a kernel disk quota.

Before every case, free space must exceed hash-proven outstanding cohost
reservations, next-case cap, cleanup reserve **and** the original2GiB margin.
Conservative floors retain producer6GiB, future clone6GiB, clone headroom1GiB,
observer128MiB and original-other1GiB. If existing plans reserve more, register
the larger amount with its original evidence pointer. The runner does not
lower budgets or infer unused capacity by opening a live financial DB.
Case cap is at most64MiB, aggregate at most512MiB; combined financial/log
growth is checked. Missing reservation evidence is a refusal, not zero.

## Timing amendment and historical appendix

The only benchmark change is `measurement-footer.json`, written directly at
the existing `settled = monotonic_ns()` capture, before feed shutdown and
`router.close`. It records original start, actual end of terminal observation,
planned duration in integer ns and setup/close exclusion. The original summary
formula is unchanged. The footer is manifest-covered. The runner rebuilds
`max(planned_duration_ns, settled-start)`, verifies all raw completions are no
later than settled, then derives the rate and drain arithmetic.

The earlier independent review's denominator result for the old136 micro-
arrivals checked summary arithmetic and a raw-completion **lower bound**.
Those old records have no observation-end footer, so exact independent
denominator reconstruction was impossible. No footer has been backfilled and
no old result is upgraded. New footer functionality is tested once with eight
real synthetic arrivals over0.05s; it is not performance evidence. Original
source hashes, receipts and RO reconciliation are retained separately.

## Delivery and rollback

This slice has pure fixture checks, short owned dummy lifecycle/overrun tests
and one eight-arrival footer call-through. There is no variant execution or
new qualification claim. New final-source full QA, CI, package, independent
runner review, actual cohost/reserve registration and an explicit quiet-window
GO remain integration dependencies. Update the registration only in a new
file; keep every failed/UNKNOWN execution directory.

Deploy the tool by checking out the qualified source and preparing first.
Rollback stops using this external runner for future cases, preserves owned
authorities/IDs/logs and investigates incomplete cleanup; it does not rewind
financial history or kill cohost jobs. Any financial binary rollback still
must preserve irreversible durable-batch capability and pending recovery.
