# Managed soak recovery and long-run blocker

This recovery session did not run another smoke or long job. It did not open a
SQLite connection, signal a process, modify storage code, or touch the original
887/observer authority. Work resumed in `/workspace/uta-managed-soak` on
`feat/managed-soak`, initially clean at `70dc281` (tool candidate `d73f4ed`, base
`4c68f01`). Its five existing commits and original raw observations are retained.

The newly identified SQLite POSIX-close issue remains a separate release gate:
https://www.sqlite.org/howtocorrupt.html#posix_close_bug. A short green workload is
not evidence of process lock ownership. Base storage fixes alone also cannot
qualify subsequently added database overrides in diagnostics or read views.

The tool now blocks every run/resume longer than 60 seconds before creating or
modifying job state. Neither `--allow-long-run`, dirty development, nor a direct
Python API call bypasses it. The same blocker prevents positive 6/24-hour report
flags. No capability-name detection or single-patch hash declares a release
safe. A later candidate can consume the actual full-release validation summary
and compare every current `uta/*.py` and tool/dependency source hash, after root
provides that complete approved evidence. This version does not implement such
an approval input or remove the blocker.

Only the two pure long-job gate tests were executed under Python 3.10 and 3.12;
they cover opt-in refusal, CLI/direct-API refusal and read-only inspection of a
long resume configuration without creating a lock/checkpoint/authority. Raw
outputs are retained. They perform no bootstrap, TLS server, worker, financial
transaction or SIGKILL. The historical integration test results remain historical.

`verify_archives.py` independently checks the committed artifact bytes without
importing the runner or financial engine. It verified four archived cases, 36
SHA-256 file references, 607 hash-chain events, and four synthetic financial
snapshots with integer per-event/per-currency journal balance, projections,
fees, cleared debt, real match/fill counts and decision links. It opened zero
SQLite connections. This verifies archived integrity/arithmetic; it is not a
fresh financial execution or validation of the POSIX-close fix.

Original case payload files and candidate commits were unchanged. README scope
notes were added and the final bundle's README checksum was updated with its
prior checksum retained in `scope_notes`. No earlier observation is relabeled
as evidence for a repaired release, a long run, capacity or production approval.
