# Process readiness: source-only candidate and once-run proposal

Status: **CODE/SPEC only at this freeze; no candidate test or native run has occurred.**
The source-only commit `2d12a2e488bd1d2df3599f8c8e15cb9217573264`
was not executed. This revision adds the parent's requested late-return check
and strictly typed identity checks before the one authorized pure batch.
Parent source is `8d6e7852689851f56801768de65506242f9d4c46`. This candidate
changes test orchestration and diagnostic retention only. It changes no UTA
runtime, market validation, lease, risk assertion, CI workflow or timeout.

## Original failures remain separate

The immutable independent evidence commit is
`bc04c9fb7a4de4e93dcf4a46b93b2fc2920da0f6`, for PR34 first PR run
`44217846755`, Python3.12 job `134512043520`. Its original failure archive is
artifact `14389736273`, 95,159 bytes, SHA256
`8319cce1677ddac774b26e4f6530ea4d8b7f673798ec4a4a45b021d74f3a5a02`.
That invocation had 1,835 tests, two FAIL, zero errors and zero skipped. The
successful first push and the five successful batch-contract methods do not
replace either failure. No original test or suite has been rerun here.

1. `test_malformed_missing_and_oversize_persistent_quotes_fail_closed` failed
   during its first `activate()`, before entering the corrupt-quote loop.
   The observed reason was `market_stale`. The retained report also shows
   shard0 live PID4984/generation2 with an older READY PID4978/generation1,
   and shard1 live PID4985 with an inactive lease owned by PID4979 and a
   failed `lease_expired` report for PID4979. These are observation facts.
   They do not establish when or why ownership changed or the quote aged.
2. `test_same_version_changed_persistent_content_is_not_reused` passed its
   original corrupt-content checks and recovery `activate(market2)`, then
   failed the next independent `financial_ready` assertion. No diagnostic
   payload was retained there. Its failing predicate and cause remain unknown.

Neither failure proves a scheduler cause, a harmless batch change, or the same
cause as the other failure. The first-run RED remains the integrated result.

## Proven runtime boundaries

Source references below refer to the unchanged parent runtime.

- `durable_process.py:1273-1310`: `start()` spawns and starts the monitor,
  then returns. It does not wait for owner READY.
- `durable_process.py:476-525`: each real spawned child acquires its own
  PID-bound writer token and completes owned initialization before sending
  READY; the batch path also resolves startup batches and renews before READY.
- `durable_process.py:1329-1330`: the monitor alone consumes READY into
  `_reports`. Successful command receipts do not prove consumption.
- `durable_process.py:1471-1474`: native `owner_ready` requires a live current
  child, matching process/lease/READY PID, active lease, and matching current
  lease/READY generation. A frame alone is insufficient.
- `durable_process.py:1382-1515`: each diagnostics call starts false and
  independently reads persistent state. It rechecks its original lease
  observations and market freshness at the end. An actual later renewal
  cannot turn an earlier conservative read into a cached success.
- `durable_process.py:1557-1624`: complete publication and activation receipts
  do not guarantee readiness in a later diagnostics call.

`ProcessReadinessTests` retains market age2s, lease1s, publish8s and kill-switch
8s. The existing `wait_ready()` sampler uses its actual default1s, with each
diagnostic bounded by .1s. There was no single end-to-end8s activation budget.

## Candidate behavior and proof limits

`tests/readiness_before_quote.py` introduces a test-only barrier for **new
default quotes only**:

1. Within one total second, observe parent-consumed READY frames matching all
   current live children. This warmup reads only the mutex, process objects and
   `_reports`; it does not repeatedly acquire diagnostic SQL during startup.
2. Take exactly one native diagnostics observation, using at most .1s of the
   remaining budget. Retain the complete returned report, record the return
   completion monotonic time, and fail if it is at or beyond the original total
   deadline, even if the report itself says the owner was ready. This check does
   not reserve a future scheduling interval after the final observation.
3. Require one complete current owner witness: supervisor/current children
   alive, observed control, active leases, native `owner_ready`, and exact
   shard/PID/generation matches. Reject top-level observation errors, timeout,
   per-shard timeout and guard errors even when owner fields are already true.
   The only permitted shard states are `ready`, or `market_missing` while the
   control has no published market version. The latter is the expected initial
   absence and does not assert market or funding readiness.
4. Create the new default current quote after that witness. A failed or unknown
   first native observation fails this attempt; there is no native resampling,
   renewal, republish, new SID or timestamp rewrite to obtain success.

The witness proves only that bounded observation. It does not reserve the
owner, prevent later expiration or respawn, prove financial readiness, or
guarantee the next call. The normal runtime predicates still decide all later
publication, activation and readiness outcomes.

Explicit `MarketSnapshot` objects bypass quote creation exactly as before;
their identity, version, timestamp and content are unchanged. Real expiration,
clock rollback, persistent-content corruption and exact-generation assertions
remain intact. The final same-version recovery check still performs a new
diagnostics call and asserts its own result; it now includes the complete
returned payload on failure. `wait_ready()` retains its chronological samples
and includes earlier unknowns in subsequent fatal failure messages.

Identity fields are native Python integers: bools/floats that compare equal to
a shard, PID or generation are rejected both in the parent frame gate and the
native witness. The report-shape input domain is the production diagnostics
dictionary, not a general malformed-object parser.

The pure reference fixture has seven methods. It can check test orchestration
only: first unknown retained with one diagnostic and zero factory calls;
owner witness precedes quote creation without promoting financial readiness;
PID/generation/lease mismatch rejection; late top/shard timeout and guard
error rejection; unmatched consumed frame cannot reach diagnostics or quote
creation; a fake clock makes the sole diagnostic return exactly at or after
the total deadline; and equal-valued bool/float identities are rejected.
Only the pure helper reference clock is patched in those cases. No actual
native clock is patched. Synthetic fixtures cannot validate native readiness
or either CI failure's cause.

## Frozen validation proposal; no execution authorization in this record

The exact revised source hashes are recorded in `source-plan-v2.json`.
Any source edit requires a new source manifest and plan revision before a run.

The parent agent authorized exactly one revised pure batch, CPU1 / wall10s,
at most eight methods, with first raw retained and no retry. The frozen runner
selects exactly the seven reference methods once:

```sh
python -I evidence/reviews/process-readiness-engineering/run_pure_once.py FROZEN_SOURCE_COMMIT
```

This invocation imports only the standard library and the new test helper. It
must not import UTA, SQLite, start any router/worker/service, send a signal or
use the network. Its first stdout/stderr, exit status, runtime version, source
hashes and exact invocation must be retained whether PASS or FAIL. The runner
pins itself to one CPU from its own existing affinity, prohibits UTA/SQLite
imports, and checks a10s wall budget on Python line events. A budget failure
flushes a raw event and exits this interpreter; it does not signal a process.
This is sufficient for the statically reviewed, nonblocking pure cases, not a
general timeout wrapper for arbitrary blocking code. No rerun is authorized.

Native evaluation is a **separate, unapproved future scope**. Before proposing
it concretely, prepare a small resource preflight and source-frozen once driver
with an append-and-flush journal for every actual parent diagnostics return,
including the first unknown. The wrapper must return each original report
unchanged and must not patch clocks, leases, READY, market checks or results.
Record quote identity/time, ordered phase boundaries, publication/activation
receipts and the independent recovery observation. Preserve private first raw
outputs and derive safe public records from them.

The first proposed native case is exactly
`ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed`,
once, in a new private temporary authority, with at most two owned workers at a
time. Every original corrupt-quote subtest must remain effective; an initial
failure is a failure before those checks, never evidence that they passed.
Wall/output limits, interpreter, source pin, owned-child cleanup and preflight
must be explicit in that later reviewed scope. No original suite rerun,
unrelated process inspection/control or blind retry is included.

The same-version recovery case requires its own once scope and remains
unexplained until its independent raw diagnostic is observed. A new candidate
PASS would be a distinct result, not replacement of the original two FAIL.
