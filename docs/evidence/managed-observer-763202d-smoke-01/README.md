# First 763 minute smoke: financial pass, live coverage incomplete

One actual synthetic 60-second job ran after root's explicit short-smoke GO.
No second job or six-hour job was started. The selected source was
`763202df9cb3ce089721e5281371aff3eab58089`, with the genuine matching Python
3.12 report (1,110 tests; report SHA in `summary.json`).

The actual driver was PID 112119, birth 4178480. Measured launcher time was
2026-11-17 08:37:38.328051 UTC; producer exit was 08:38:40.045158 UTC.
Producer active time was 60.165944236 seconds, with all 15 planned rounds,
three worker faults and one parent fault completed. The actual private-clone
producer cold audit was recorded at 08:40:03.436266 UTC, 145.108215243 seconds
after launch, inside the 150-second outer bound. Later work only preserved
evidence and tested the launcher on ordinary temporary files.

The final independent integer/relational oracle, integrity/FK checks, actual
reopen and same final watermark passed. Final counts were 90 terminal account
commands, 30 control commands, 60 orders, 60 fills, 30 matches, 120 required risk
decisions and 81 journal events. All gross debt was repaid, positions/orders were
flat and no internal retries were observed. All 313 checkpoint events were
covered by verified exported logs. The actual report-selected Python ran the
unmodified producer `audit` CLI on the bounded private complete clone, with
equal before/after original business/checkpoint watermarks.

**Live observer coverage is INCOMPLETE.** The original `live-01.json` is retained
byte-for-byte: PermissionError produced unknown and no pass. Diagnosis found
the read-only root mount prevented this container's `/dev/null` from being opened
by subprocess DEVNULL handling. The trusted outer wrapper was then corrected
to supply Bubblewrap's standard fresh `--dev /dev`, with the job and source
remaining read-only. No producer, authority or frozen f6f observer core bytes
were changed. `wrapper-device.patch` records the exact wrapper change used for
the successful final/cold steps. The first smoke is not described as a complete
observer pass, and it did not obtain normal active/fault-period coverage.

The final stale progress/market age alerts are preserved; no fresh feed was
invented after completion. The long-run audit gate really rejected the short
job and no long-run receipt exists. Every six-hour, 24-hour, production, 10k and
final eligibility flag remains false.

`outer-mount-probe.json` records a separate ordinary-file namespace probe:
actual job/source mount flags read-only, selected output writable, attempted
write to a temporary plain read-only sentinel denied with EROFS, fresh
`/dev/null` a character device, and a DEVNULL subprocess successful. It opened
no original job data. The revised tiny suite passed 51 tests in 1.379 seconds
on one allowed CPU; these probes did not run another service.

`manifest.json` hashes the explicit public/synthetic export allowlist and records
original artifact timestamps. No `private/`, authentication database, TLS key,
raw stderr or nonce-bearing private complete clone was archived. A second
minute smoke requires another explicit root GO after the wrapper fix is frozen.
