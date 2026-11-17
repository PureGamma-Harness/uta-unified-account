# Expired paused shared-gate owner: investigation plan

Frozen source: `d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6`.
This independent investigation uses `/workspace/uta-expired-publication-review`
and changes no implementation or original test. The source freeze and all
pre-existing financial authorities/processes remain untouched.

## Original evidence

The Python 3.10 full run executed 1413 tests, with 1 failure, 0 errors/skips,
unchanged clean source and final `passed=false`. The failure is
`ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`,
at the `done.wait(5)` assertion. Its message attributes the wait to an expired
live PID retaining SH flock, but the original log contains no phase timings,
PID exit facts or publication result at the five-second boundary. That message
cannot prove that exact cause.

The original summary, worker result and complete unittest log are copied without
editing. All **252** before/after input hashes agree with the fixed source's
actual files and Git blobs. The complete original test file is also preserved.
See [raw evidence](../evidence/runs/expired-publication-d421/copies.json) and
[source verification](../evidence/runs/expired-publication-d421/source-verification.json).

## Static facts and uncertainty

The test starts two genuine spawned workers with a one-second lease. It pauses
both only after acquiring the router EX gate and SQLite writer, resumes shard 0
while its actual SQLite writer is blocked, observes SH gate contention, pauses
that owner while it holds the gate, then resumes the other shard.

The publisher calls the actual `publish_market(snapshot, timeout=5)`. That API
uses separate bounded phases: initial EX gate, persisted publication/enqueue,
five-second shared receipt deadline, and final EX gate. The test's outer
`done.wait(5)` is not a documented total API deadline. SQLite calls, scheduler
pauses and child startup also occur inside those phases; their contribution
must be measured rather than assumed. This observation does not prove why the
historical five-second wait failed.

The supervisor polls every .05 seconds under its own mutex and uses an actual
read-only fence observation with .1-second SQLite timeout. It kills only its
own still-live child whose matching owner PID has expired, joins it, and spawns
a replacement. The publisher does not acquire that mutex. No deadlock is
inferred from the existence of the mutex alone.

## Authorized baseline reproduction

Run the **original single case once** on Python 3.10, preserving its exact
parameters and code. An external watchdog bounds the whole subprocess group to
30 seconds, including cleanup. Its scratch directory, group and births belong
only to this reproduction; no existing job or affinity is readjusted.

An external call-through recorder may observe parent-side operations without
changing their return values, exceptions or waits:

- old and replacement worker PID/birth, actual kill/join/exitcode and generation;
- actual fence status results, including unavailable observations;
- publication v2 start/end, initial/final gate acquisition, receipt phase and
  exact original per-shard publication IDs/states;
- the original outer Event wait, publisher thread completion and cleanup;
- final own-scratch orders/events, with no more than one financial admission.

The trace itself may add observation overhead and will be labelled accordingly.
No extra delay, altered clock, fake SQLite status or fault result is permitted
in this baseline. A successful original run is recorded as **NO_REPRO**, not as
proof that the earlier failure did not occur. A watchdog or incomplete trace
cannot become a passing recovery result.

## Decision before a repair

If the actual old binding remains live after expiry or its gate is retained,
report a runtime defect with the concrete phase and propose its narrow scope
before changing implementation. If the owner demonstrably exits and the
original publication progresses, separate those facts from the test's total
wait assumption. No production lease, five-second API parameter, retry policy
or financial assertion will be relaxed.

A test-only repair, if independently reviewed and authorized, must separately
prove the original binding's exit, generation increase, gate release, success
of the original publication IDs, and financial count <=1. Any broader
thread-lifecycle watchdog must have an explicit phase-derived purpose; merely
changing 5 to 15 and calling it a recovery pass is not acceptable. Controlled
red/green experiments require the integration lead's review after this plan.

No controlled reproduction, runtime fix, new stress load or production approval
has been performed by this plan. `production_approved=false`.
