# Independent engineering review of the old observer contingency

**ACCEPT the256MiB contingency for synthetic cohosting with this fixed old
observer, subject to fresh admission checks.** This is a sizing decision,
not a hard cap, allocation, disk reservation, guaranteed growth bound or
permission to start a new six-hour job. The new source still needs all release
gates; source91 remains NO_GO. Final free space must be remeasured by the
integration owner after the new full QA/package work.

## Allowed observation and actual occupancy

Review source is b3460957978f9c1ea7c3a844fa45d86bae3274b2. The scanner reads
only the existing original progress/latest JSON, selected /proc identity and
allowlisted CLI metadata, source files and nofollow directory metadata.
It never opens database contents, runs producer status, sends signals or
changes either old process's affinity. The scanner's own short execution used
CPU3. No service or workload was started.

At2026-11-17T14:40:22.205393 UTC, the scan completed in0.0157s. The old
observer held1,016 regular files, including991 observation JSONs, with no
subdirectory, symlink or special file. Logical bytes were5,919,541; allocated
regular-file bytes were8,425,472. The largest observation was5,768 bytes.
All matching private external .soak-observer-stage-* directories were
conservatively metadata-scanned; their current regular-file bytes totaled0.
Their listing is not claimed to identify the particular process's stage.

The original4471/210004 and8784/412799 PID/birth pairs remained living with
matching UID, boot6339d4fc-a9e7-4c10-a591-1e70a14322ff and unchanged observed
affinities across this scan. No old affinity was set. Both original source IDs
and deadline remained consistent in existing JSON. The observer entrypoint's
actual bytes equal immutable f96dfd8 and its recorded script SHA
5329bcdb2668eda44635558f4153305306be608cb3803099c61e50dbc26e2efd.
The producer entrypoint also equals its immutable88755a9 Git blob. These are
metadata/source checks, not a new financial or runtime-memory attestation.

Only the allowlisted observer CLI field --interval=60 was retained. There was
no --max-bytes or --max-observations override. Exact f96 CLI code therefore
uses watch's default64MiB post-write software threshold and its18,000-record
check. The watch function permits max_bytes up to256MiB when called directly,
but that is not a recorded CLI override here. Neither the64MiB writer-loop
check nor its older documentation's “hard” wording establishes an OS byte
quota: a large write can precede checking, and external atomic staging has
transient space. The review does not modify that old source or configuration.

## Remaining window and explicit assumptions

The original producer deadline remains2026-11-17T21:36:13.820942Z, raw epoch
1794951373820942405ns. At capture there were24,951.616 seconds remaining.
Observed snapshots are about5.7KiB every60 seconds. The observer writes fixed
observation JSON, a growing manifest, latest and hourly copies, with a single
atomic temporary file per write; this source performs no bulk clone copy.

For contingency sizing, use a deliberately larger **assumption**, not a bound:
64KiB per future observation plus512B manifest growth, hourly64KiB copies,
and3MiB for latest/staging/final metadata. It yields27,447,808 additional bytes
for the next six hours, or31,212,032 through the original producer deadline.
Adding all currently observed logical bytes and stage bytes remains far below
268,435,456 bytes. The assumed record size exceeds the observed largest by
more than11 times; the256MiB floor exceeds the six-hour stressed increment by
more than9 times. This provides reasonable engineering room for the unchanged
synthetic profile. Unexpected payloads, error storms, filesystem allocation
behavior or later observer changes could violate that projection; no physical
maximum or assured peak is claimed.

The contingency is additional future room. Existing occupied bytes already
reduce actual filesystem free space and are also conservatively included in
the size comparison above. It does not replace the old producer's full6GiB
future reservation or reduce another component's declared budget.

## Freshness and launch conditions

At the original capture, current progress's effective heartbeat age was
2.793s and the old observer's original assessment plus its elapsed JSON age
was23.409s. Both are below30s. The latest JSON itself was19.869s old; it was
not disguised as a new producer heartbeat by the scanner's current timestamp.
The scanner's capture window was much less than15s.

The snapshot TTL is15 seconds: this record expired for actual admission at
14:40:37.205393 UTC. The engineering sizing decision persists only for the
same fixed source/cadence/output profile; it does **not** keep this metadata
fresh. A later start must capture new original progress/latest and process
metadata and recheck both effective heartbeats<=30s, the same source/PID/birth/
boot and no alerts. Missing, stale, changed or unreadable metadata means NO_GO,
not a default healthy value or a refreshed observation time. Normal61/60-second
observer cadence does not waive the admission heartbeat rule.

For a newly qualified synthetic attempt, source6GiB + output2GiB + clone
admission estimate1GiB + headroom1GiB is10GiB. Old producer6GiB + this256MiB
contingency brings the combined requirement to16.25GiB, exactly
17,448,304,640 bytes. The integration owner must recheck actual free bytes
against that threshold after full QA/package and immediately before the new
attempt, alongside the fresh cohost metadata. No current disk observation or
arithmetic margin in this review authorizes launch. Clone admission and
observer thresholds remain estimates/periodic controls, with no guaranteed
overshoot bound. There is no capacity, old24-hour pass, new six-hour pass,
financial correctness or production approval here.

## Evidence and rollback

The nofollow scanner, complete metadata rows, source proof and TTL/assumption
interpretation are in evidence/reviews/old-observer-contingency/. Existing
progress/latest bytes are fingerprinted; their financial database snapshots
were not reexecuted. All output is new review material. Reproduce only as an
authorized metadata capture with a new --output filename; existing captures
cannot be overwritten. The scanner's output marks actual launch GO false.

Rollback is docs/evidence-only. It must not edit the old observer, its output,
its source, its original clocks or its processes. If future sizing assumptions
or freshness/free-space conditions fail, defer the new synthetic attempt and
retain the failed capture; do not gain room by altering the old24-hour job.
