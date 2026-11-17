# Preregistration: 16-sample recovery diagnosis, no qualification rerun

Status: **not executed; root GO and final runtime bindings pending**. This plan
is a causal-diagnosis experiment, not a source91 release rerun or acceptance gate.
The first local Python 3.13.5 case remains the single immutable observation in
`b5707fe319cf4f07c64e34e8a62f130e5a135803`: original case PASS / historical
failure NO_REPRO / strict observer evidence incomplete. No new flag or later
result is written into its raw files, helper, derived report or conclusion.

The original CI at source `91e4ae40b5e9b884c54026406299df5000c9c100`
reported the bound old PID failing to exit within five seconds. Its cause remains
UNPROVEN. Publisher-entry expiry alone cannot explain independent supervisor
liveness. We seek original failure traces, status-call timing/errors, monitor
code locations and owned-PID lifecycle that can distinguish the hypotheses.
No runtime or original test fix is part of this experiment.

## Fixed design, before observing any new native outcome

Sixteen new independent samples use order `ABBA ABBA ABBA ABBA`. Each consecutive
pair is AB then BA, repeated four times; each runtime receives eight samples.
IDs are `s01-A`, `s02-B`, `s03-B`, `s04-A`, `s05-A`, `s06-B`, `s07-B`, `s08-A`,
`s09-A`, `s10-B`, `s11-B`, `s12-A`, `s13-A`, `s14-B`, `s15-B`, `s16-A`.
A is current `/usr/bin/python3.13` (observed Python 3.13.5); B is an official
Python 3.13.18 build whose location, binary SHA, source-tag provenance, complete
runtime identity and SQLite version must be bound by root before GO. Until then
B is explicitly unresolved and this preregistration authorizes no execution.
Using the official version still does not reproduce CI's compiler, image,
scheduler, kernel or I/O environment. Host build/provenance differences remain
confounders; no version-only causal claim is allowed from a single failure.

All samples use the same exact91 financial code and original testcase, original
fixture lease 5, capture horizon 5, recovery horizon 5, API phase timeout 5 and
full publication-thread lifecycle 15 seconds. Production and test files remain
unchanged. Each sample runs one original case in a fresh private directory and
fresh process session on CPU 2, with a 27-second worker watchdog and an independent
whole-invocation budget of 30 seconds. Do not widen either bound. The full
16-sample upper bound is eight minutes of whole sample budgets, plus explicitly
bounded static collection between samples. CPU2 must be scheduled without other
team components during the batch; no old job is stopped, signaled, queried or
reconfigured to obtain that capacity. Preserve actual CPU/host/runtime identity.

Every sample's BEGIN/END, command, new PID/birth/session, runtime and helper hash,
266 source hashes before/after, raw unittest output, original exceptions,
three-clock event trace, observer lifecycle and post-join state, original
publication receipts, original financial checks, and own-session scan is retained.
Do not reset a sample, reuse an old output path, replay a failed business command,
replace an original exception, discard an early failure, or repeat a sample.
All sixteen slots remain in the final manifest; unexecuted slots have explicit
NOT_RUN_DUE_TO_STOP status, never fabricated output. The first run in b570 is
context only and is not added to these sixteen planned samples.

## Safety stop and proposed ordinary-failure policy

**Recommendation awaiting root selection:** retain an ordinary original
`unittest` assertion failure and continue the already fixed remaining order,
provided that sample's technical evidence and native cleanup gates all pass.
This avoids an outcome-dependent choice of runtime exposure. An exact original
failure may justify a separate proposed production fix, but does not authorize
one during this batch. Alternative: root may preregister stop at the first
original assertion failure before GO; the remaining fixed slots are NOT_RUN,
not retries. Root must select the policy before the first sample.

Any watchdog, whole time above 30 seconds, forced cleanup (including original
fixture forced kill), residual new PGID/SID member, incomplete spawn accounting,
missing result, `unittest` ERROR, missing/corrupt events, logger failure, observer
error or live observer after join, sampling unknown, source mismatch/read error,
or runtime/helper binding mismatch stops the batch after the current sample's
bounded own-child cleanup. Preserve the original cause and raw output. Whole
batch is NO_GO/incomplete for diagnosis; do not launch the next slot, rerun for
green, broaden a timeout, kill foreign or reused PIDs, or catch arbitrary SQLite
errors as financial health. A runtime or source mismatch found before a sample
means no native case starts for that slot. Unknown native cleanup must be
escalated to root with exact own identities; it does not authorize foreign kills.
The external whole-clock and runtime-binding checks remain mandatory even if
the sample helper's internal flags are complete.

## New recorder only

`evidence/runs/recovery-horizon91/trace_original91_lifecycle.py` is a new helper;
`trace_original91.py` remains byte-identical to the original approved 81b9 helper.
The new helper retains the same call-through observations and original test,
and adds explicit pidfd/code-stack observer start/end/error events, post-join
`is_alive()` plus native clock records, and source/sampling/logger safety flags.
Both observers must have started, ended without error, and be nonalive after
join. Logger or sampler errors remain technical unknown; they cannot be hidden
by case PASS or by the eventual worker exit. Private output mode 0700 is set in
the helper as well as the external launcher. A new own-session read-only native
scan and spawn/event integrity flags close the batch safety-stop decision; no
new financial SQL or original status call is introduced.

After root and independent static review, final execution instructions must bind
new-helper SHA, preregistration SHA, source SHA, both actual interpreter paths/
SHAs/identities, output root, chosen ordinary-failure policy, and an exact bounded
batch controller. This preregistration alone is not permission to run it. No
native sample or full-source suite has been run while preparing it.

Report all attempted and unattempted slots, exact failure stages, runtime counts,
raw timings and observation incompleteness. Sixteen PASS results would mean only
NO_REPRO under this registered design, with the historical failure and production
qualification unresolved. One failure is a diagnostic observation, not proof of
a unique runtime cause. A validated fix needs its own concrete scope, independent
review and fresh acceptance evidence.
