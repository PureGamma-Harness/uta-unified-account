# First real adapter attempt: failed before data-child creation

Root authorized exactly one new real synthetic filesystem/pipe adapter at
input source `dc1e8e6c37e98a0d33c7d2aafc8af96ffca7ee4d`, frozen tip
`cef70d81fabb530dbc8c36509558aff8d7412693`. That attempt returned exit1 in
99745469ns. All eight input files matched Git byte-for-byte before and after.
The budget is consumed. There was no retry, source change or old test rerun.

The first original traceback stops inside actual `Pipes.__init__`, its
restricted ChildAPI.Popen, and CPython's `_get_handles`/`_get_devnull`:
`os.open('/dev/null', O_RDWR)` was rejected by the probe's directory write
audit with `adapter_write_outside_new_output`. This was an overly broad test
guard for a standard Popen descriptor setup operation. It is not evidence of
a trading, financial-verifier, report-codec or `read1` runtime failure. The
constructor did not return, no data-child identity was established and the
probe's subsequent try/finally was not entered. The traceback location is the
basis for identifying the pre-spawn phase; missing identity is not called a
successful reap or cleanup proof.

The new owned0700 parent/output were created only at the authorized path.
The output contains the609B immutable probe intent and0B original emitter
stderr, plus empty node/receipt directories. No CAS node or receipt was
published. Control/observer regular-file measurement was609B against131072B.
Original outer stdout250B and stderr1701B total1951B against102400B; those
diagnostic bytes are explicitly separate. The48KiB-per-regular-file capture
limit was not reached. No timeout was reported.

First raw stdout/stderr, one-run root intent, launcher/source hashes,
before/after source closure, actual timeout-process identity, exit and file
manifest are sealed under
`evidence/observer-compact-report-v2/adapter-first-once01`. The two new probe
files were copied byte-for-byte into `probe-first-originals` with O_EXCL;
the original external files remain in place. The source-budget's original
allowed-runs0 record is unchanged. No secret or account data was used.

The live-small-frame condition, real two-frame backpressure, wire hash/EOF,
read-only exact reconstruction, receipt idempotency and quota negative were
**not reached**. No adapter pass, native timely-small-frame proof, successful
cleanup, financial acceptance, six-hour stability, capacity or production
approval follows. Original e9 mock12 PASS and all earlier first FAIL/UNKNOWN
records retain their separate scope.

A future candidate must address standard descriptor setup without granting
arbitrary writes outside the fresh output, retain this first FAIL, and pin
its own source and independent review. Any later actual execution requires a
new concrete root authorization and new path. This report grants no retry.
No old output is renamed, removed or used as a replacement first run.

Rollback remains unchanged: leave report mode legacy by default, retain all
evidence and do not launch or resume a long run. No data migration occurred.
