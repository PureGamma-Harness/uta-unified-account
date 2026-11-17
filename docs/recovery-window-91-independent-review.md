# Independent review of the original 91e recovery-window failure

The original push run `44104161669`, Python3.13 job `134111871255`, artifact
`14337038689`, executed 1,512 tests and retained one failure with zero errors
or skips. Its bound stopped PID did not produce a pidfd exit observation in
`test_durable_faults.py:1525` within the unchanged five-second recovery horizon.
This is **NO_GO**. The other seven complete CI jobs passed; they do not override
this failure. This review performs only source/AST and original-byte inspection,
with no SQL, process injection, test rerun or gate change.

The fixed implementation under review is
`91e4ae40b5e9b884c54026406299df5000c9c100`. The exact original raw members are
retained by evidence commit `07b0381eef9d6b9a03d0b62b6b7bd1ec1fc81178`.
Their byte hashes and actual result counts are retained in this review's
`original-failure-reference.json`. The review's pure source inspector compares
four current files with their exact source Git blobs and records eight narrow
AST facts. Its own passed structural assertions do not establish recovery
liveness or a cause for the original failure.

## What is established by source

The fixture waits until a fresh lease has at most 250ms remaining, then creates
and starts a publication thread. That thread opens another original native
lease observation, asserts that the original PID/generation is still active,
and only then invokes the original `publish_market(..., timeout=5)`. A scheduling
or observation delay can invalidate that short entry window. Any thread error
is appended to the local `errors` list and sets `done`. The parent immediately
waits for old-PID exit and asserts that result before checking `errors`.
Consequently a publication-thread entry error can be hidden behind the parent
exit-window failure. The original failed log does not dump the fixture's
`publication_thread_entry_lease`, `publication_called_api_at`, `errors`, or
supervisor stack, so it cannot identify that path.

**A publication entry failure alone does not explain an old PID remaining alive
for five seconds.** The production `_supervise` thread independently visits
workers after `Event.wait(.05)`. For a living worker it obtains a native lease;
when the observed lease names that PID and is inactive, it kills that owned,
unreaped child and joins it. This decision does not depend on publication being
invoked. A complete cause for this failure therefore must also explain why
supervision did not observe/act on the expiring selected binding in time, or why
the pidfd exit observation was unavailable.

The single supervisor holds its `_mutex` while visiting all workers. Its
`pipe.poll()` and subsequent `pipe.recv()` are separate calls; readiness of some
pipe bytes is not a whole-frame deadline guarantee. Lease-read exceptions are
caught and converted to `None`, preserving fail-closed authority but providing
no diagnosis of repeated technical unknowns. The `.1` SQLite busy timeout is
not a deadline for the entire native status operation, which includes connection
and schema checks. Process creation, ownership registry writes and all other
shards share that supervisor turn. These are possible blocking or failure
locations to inspect, not verified causes of this CI failure.

`_spawn` does **not** wait for READY. `_record_process` directly writes the control
DB; it does **not** itself acquire the router's EX flock. Therefore the static
claim that spawning necessarily blocks on the selected worker's held SH flock
is unsupported. Other actual SQLite/process/scheduling waits would require
observed evidence. No supervisor exception banner appears in this raw log, but
absence of a banner is not evidence that its thread remained alive or scheduled.

## Required diagnostic distinctions

| Hypothesis | Observation needed | What must not be inferred |
| --- | --- | --- |
| Publisher entry expires before API | Original thread lease/time, original exception and API-call marker absent | This alone explains missing supervisor kill |
| Supervisor native observations remain unknown | Original status call start/finish, native exception attributes, thread stack and selected binding | Unknown permits kill, lease renewal, or healthy authority |
| Supervisor blocks or dies | Thread alive state, stack-only snapshot, mutex/pipe/process/registry location | An unobserved blocking path occurred in historical CI |
| Native expiry is observed for selected PID but exit misses horizon | Native PID/generation/expiry/now plus actual kill and pidfd timing | A component BUSY pass proves five-second recovery |
| Source/owner changes | Original PID/birth/boot, both worker identities, status generation/owner | A different owner grants permission to kill an unrelated process |

A single separately authorized original-case run can collect the existing
`_expired_gate_observation`, original exceptions, and periodic parent-thread
stacks using only filename/function/line number, never locals or raw financial
payloads. Wrapping the original native status call can record its original
start/finish, thread, monotonic/boottime, selected safe scalar fields and native
error attributes; it must rethrow the same exception and must not add database
reads. Include monitor alive/stop state and both worker identities, not only the
publisher. Record driver/source hashes, watchdog and whole-run budget, forced
cleanup and residual identities. Instrumentation overhead changes the observed
experiment; a non-reproduction must remain a non-reproduction.

The original five-second lease, five-second capture/recovery horizon, five-second
API phase and fifteen-second separate publication lifecycle stay distinct and
unchanged. No passing component or subsequent diagnostic run can relabel the
original CI failure. A fix requires its own concrete evidence, independent review
and fresh full-source gates; this review signs neither a five-second recovery
claim nor production readiness.

## Deployment and rollback

This is docs/evidence only, without schema, data, runtime or API changes. There
is nothing to deploy. Reverting these new review files must not delete or modify
original CI members, frozen source, private experiments, artifacts or clocks.
Source91 remains NO_GO and no real-funds or long-run approval follows.

## Concrete observation driver 5e26 review

The external candidate is `5e26f0acd04b47cdafad942464e70b537c70d30b`, following
`1ac5bb633e18634cb5e0a976ccd8efefb8af71ea`. Exact driver SHA-256 is
`81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee`.
Independent compilation/AST and 266 Git-blob hash checks passed without executing
the driver or importing the financial runtime. The original test and production
runtime bytes are unchanged. The status wrapper calls the original once and
returns or rethrows its result, without added SQL. Stack sampling excludes frame
locals; publisher error capture reads only its explicitly named errors cell.
The later candidate moved the whole timer before source preflight and records
the real interpreter/SQLite versions. Local Python3.13.5 is not CI's3.13.18.

There is no static blocker to **one separately parent-authorized CPU2/Python3.13
observation**, with these explicit conditions. Set outer `umask 077` and verify
the new output directory is0700; the driver does not itself set a private umask.
The27-second worker watchdog and reported30-second whole threshold do not impose
an OS-wide hard deadline on external IO. Final acceptance must independently AND
whole time, source hashes, logger/sampling health, observer-thread exit, no forced
cleanup or residual processes and the original outcome. Exit0 alone is insufficient.

The launcher discovers children from completed `spawn_return` records. A partial
original `_spawn` can fail after process creation but before that record, so an
empty recorded child list cannot prove no residual process. Check unmatched spawn
starts/returns and perform a read-only `/proc` scan for this new worker's PGID/SID
afterwards. No existing job may be signaled. Unknown sampling, observer failure,
watchdog, forced cleanup or residual state remains incomplete/NO_GO. A passing
original case is NO_REPRO of the historical assertion; it does not sign source91,
prove the five-second production claim, or establish the historical cause.
