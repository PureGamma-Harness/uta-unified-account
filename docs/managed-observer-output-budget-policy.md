# Explicit observer output budget (PREP ONLY)

Recorded 2026-11-17. This is a future engineering policy, not qualification or
authorization to execute. Frozen 8b7f544 remains NO_GO and its plans/profiles are
unchanged. A future exact source and separate immutable preregistration are
required before any new attempt.

`observer.output_budget_bytes` is optional. Missing means the historical 6 GiB
default and historical measurement behavior. An explicit value must be an exact
JSON integer (not bool), between 1,073,741,824 and 6,442,450,944 bytes inclusive.
Integer byte values need not be multiples of GiB. The proposed future value is
2,147,483,648 bytes. The resolver neither edits nor adds a field to old plans.

The existing supervisor only measures `observer/timeline.jsonl`, `latest.json`
and `baseline.json`. Its exceedance adds a collection error and does not request
drain. This remains the legacy missing-field behavior; it is not a complete
output-tree budget. The explicit-field policy will measure all regular files in
`control` and `observer`, including classifications, receipts, atomic temporary
files and any other outputs. Only actual direct
`observer/private-audit/private-full-clone-*` directories are excluded from the
output sum: complete private clones have a separate admission estimate and
headroom. The excluded subtree must contain no symlinks or special files;
unknown siblings are counted, not silently excluded. Measurement errors,
permission failures, disappeared entries or invalid types are unknown, never
zero. Neither policy deletes logs or lowers sampling.

For an explicit budget, exceeding the sum or being unable to measure it is a
typed technical NO_GO. Request official SIGTERM drain of this attempt's original
owned producer before attempting an error-log write. Do the same when an output
write fails; a full disk must not suppress the action. This is a resource safety
action, not evidence of financial corruption. Existing protected-PID/birth
checks remain in force. Other coverage/telemetry errors retain their existing
policy. No restart, resume, automatic next job or financial PASS is introduced.

The supervisor checks approximately every 30 seconds. This is a periodic
measurement threshold, not an OS quota, an allocated reservation, or a physical
hard cap. Growth between checks and work after drain/final audit can overshoot;
the overshoot has no guaranteed bound. The private clone limit is separately an
input admission estimate, not a peak-disk hard quota.

Future arithmetic: source 6 + output 2 + clone estimate 1 + headroom 1 = 10 GiB
(10,737,418,240 bytes). Adding the old cohost's full declared 6 GiB and a separate
256 MiB contingency floor gives 16.25 GiB (17,448,304,640 bytes). At the root's
reported package-end free-space point of 21,024,976,896 bytes the arithmetic
margin is 3,576,672,256 bytes. That timestamped observation is not a current
reservation or qualification. The old observer has no declared hard byte cap;
the contingency floor still requires independent root review and cannot be
automatically approved. Recheck actual cohost identity/freshness and free space
after the next full qualification and package build.

Producer source budget 6 GiB, duration 21600 s, 5400 rounds, worker/parent faults
30/300, supported watch interval 61 s, 12 coverage blocks, technical unknown
budget 3/max consecutive 1, clock and all final financial gates are unchanged.
Old bb34/d421/8b failures and stopped 763 evidence remain historical NO_GO.
