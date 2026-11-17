# One authorized original-case observation: historical assertion not reproduced

This is the single original Python 3.10 run authorized after
`40d7c1a`'s plan. The actual interval was **2026-11-17 13:02:23.444322 to
13:02:26.574080 UTC**, 3.130 seconds, pinned to CPU2. The original case,
lease, API timeout, outer wait and assertion bytes were unchanged. The trace
uses disclosed parent-side call-through wrappers and can affect scheduling;
it does not alter return values or native child worker code. Its 27-second
watchdog and 30-second total budget did not fire.

The testcase failed at **line1228**, `held=False`: the intended shared-gate
holder was not observed while the external SQLite writer was blocked. It never
created the version2 publisher thread and never reached the historical
line1252 `done.wait(5)` assertion. Therefore this run is **NO_REPRO for the
original historical assertion**, not a successful recovery acceptance and not
proof of its unique cause.

The actual supervisor observed the original owners expire, killed PID196100
(birth5767049) and PID196101 (birth5767051), observed their kernel pidfd exits
and joined both with exitcode -9. It spawned PID196106 and PID196107. The
persisted generation was still1 in the final pre-cleanup observations; a new
PID alone is not evidence that its acquisition or recovery completed. Both
shards had zero orders and zero ORDER_ACCEPTED events. All four recorded child
identities were absent after normal cleanup; no extra forced cleanup was used.

The original recorder's `historical_failure_reproduced=true` field classified
any testcase failure and is too broad. Its raw bytes are preserved. The
[separate derived classification](../evidence/runs/expired-publication-d421/baseline-original-once/classification.json)
explicitly corrects that interpretation; it does not rewrite the original
result or invent a publication result. The original driver, launch metadata,
complete stdout/stderr and JSONL phase observations are in the same directory
with a [copy/hash inventory](../evidence/runs/expired-publication-d421/baseline-original-once/copies.json).
All252 original validator input file hashes remain unchanged.

The static worker loop renews before entering the financial shared-gate path.
Holding SQLite's writer therefore does not, by itself, force a resumed worker
to reach SH before renewal. The trace did not instrument the child's exact
blocked syscall, so this remains a feasible setup issue rather than a unique
attribution of this run, much less of the original full-suite failure.

No second original run, controlled red/green, runtime fix or production approval
has been performed. Further test setup/lifecycle code awaits independent review.
