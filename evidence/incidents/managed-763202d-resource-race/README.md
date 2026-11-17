# Original 763202d six-hour attempt: terminal incident record

The attempt stopped early. Its six-hour gate, financial-final evidence gate and
live-coverage gate are **NO_GO**. This is a correction to any later assumption
that the original process was still running; the earlier 10:27 JSON/proc
handoff remains a historical observation, not a current-status assertion.

Original producer: `763202df9cb3ce089721e5281371aff3eab58089`.
Original observer/supervisor: `ce3045f66456c1592858d0297f90a9552c7500dd`.
Both frozen roots remained tracked-clean during this read-only capture. The
new incident tree is `/workspace/uta-managed-resource-incident`, initially
based on exact producer 763202d. No original job, source, timing or control file
was changed, and no process was signalled, restarted or resumed.

The original active-start boottime is `46796458020699` ns and deadline is
`68396458020699` ns. The original clock mapping is
2026-11-17T10:01:09.980709Z to the nominal 16:01:09.980709Z deadline; the latter
is not a completion timestamp. Supervisor-observed producer exit is recorded
as wall ns `1794911743053343432` (approximately 10:35:43.053344Z).
The producer measured only **2072.722098933 active seconds**, 513 of 5400 DONE
rounds, worker/parent fault signals 17/1 rather than planned 180/18, one
controller session, and exit code 2 with `status=paused`. `logs_verified=true`
is retained as its actual report; `final_audit=null`. It is not a final
independent financial reconciliation. No later uptime can extend that active
measurement to 21600 seconds.

The final supervisor report records no official-driver-drain request and an
empty historical financial-invariant-alert list. Coverage has 36 observations,
12 technical read unknowns (10 OperationalError, 2 ValueError), maximum three
consecutive unknowns, and one stable compared golden in block 0. The other
golden states are 23 inflight/unproven and 12 unavailable; empty alert lists
never convert those into financial PASS. Only block 0 was satisfied. The
already failed 250k large-history gate remains separate and unchanged.

The progress error is `FileNotFoundError` for
`<ORIGINAL_JOB>/job/managed/shard-0000.sqlite3-wal`. The original producer's
`ManagedSoak._resources()` first collects `is_file()` results and then performs
a second `stat()` for sizes. SQLite WAL/SHM lifetime permits disappearance
between those two calls. An OSError from `status()` propagates to `run()`, which
records paused, officially stops its own services, exports/audits logs and
writes the final progress. This source path explains the observed error and
early exit. No historical stack or file-lifecycle trace was retained, so this
is not a claim to have witnessed the exact interleaving or its unique timing.

All three final observer operations returned ValueError with digest
`0d86d74f3a2cec5f03901f72333631a16669a983a8aef2df180b476eb41d9f92`.
That exactly equals SHA-256 of the source literal
`wal_sidecar_snapshot_unavailable`. In frozen core `Observer.sample()`,
`self.cold` requires progress `completed`, matched original driver stopped,
and the existing baseline. Original progress is `paused`, so sampling retains
the live-sidecar requirement and fails at the first unavailable SQLite
sidecar pair. The public error has no database/phase tag; the precise first
database cannot be independently attributed from the digest alone.
`producer_audit()` calls `sample()` before checking final eligibility, so its
same error precedes its strict-long gate. Its audit CLI did not execute. Even
if those reads had succeeded, the original 2072-second/513-round attempt could
not satisfy the unchanged 21600-second/5400-round receipt requirements.

Future resource fix proposal: one `stat()` observation per discovered path;
only ENOENT for explicitly known SQLite WAL/SHM or legitimate atomic-publication
temporaries may be skipped. Surviving auxiliary files still count toward the
original disk/free-space budgets. Main-file disappearance, unrelated missing
files, permission errors and other I/O errors must propagate. Test first with
actual temporary SQLite sidecar lifecycle and deterministic directory/stat
interleavings; no service or long job is needed. No resource fix may alter
duration, planned rounds, budgets, fault schedule, resume rules or PASS gates.

Future cold diagnosis requires a separate, explicitly nonqualifying stopped-job
path: retain original immutable identities and baseline, prove relevant PIDs
stopped, independently establish the actual sidecar state, create only a
private complete authority clone through an appropriate SQLite backup, and
run the real producer cold audit there. The original strict receipt path must
continue to reject this incomplete attempt. A stopped paused job must not be
renamed completed; no live immutable read, raw active-inode open/close,
projected/deleted-nonce authority or public complete clone is acceptable.
This proposal awaits root review. **No SQL, cold clone, new observer sample or
new service was executed for this incident record.**

The archive contains an explicit allowlist of 15 previously published public
JSON files, all 36 original timeline samples and classifications, original raw
SHA-256/size/mtime metadata, frozen source hashes, and matching proc metadata
for 25 published identities. Timeline exports retain the frozen observer's
public projection, including complete redacted CID diagnostics. The original
job path is replaced by `<ORIGINAL_JOB>` in exports. There are no authority
databases, TLS/HMAC/authentication files, nonce columns, argv, environ or pipe
stream reads. At capture the original driver/CLI and all other published
children were absent; supervisor PID 122905 matched birth 4679488 and was
zombie, parent 1. These are multiple JSON/proc publication points, not one
logical database snapshot and not eligible final evidence.

Financial scope remains independent full-journal hash, per-currency posting
conservation, owner/asset reconstruction and business joins. Complete
`uta_events` business-state reexecution and full risk reexecution remain
unmeasured/null. All future/production/10k flags stay false.
