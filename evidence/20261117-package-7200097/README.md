# Frozen release package acceptance: 7200097

Source commit: `7200097ce9f92fa678907bee9a99933f60d65bc3`.
Frozen checkout: `/workspace/uta-durable-final-7200097`, kept unchanged and clean.
External work: `/tmp/uta-release-7200097-K7DuS0`.

The actual fresh build passes the complete source/archive and installed-wheel
checks. All **862 tracked source/evidence files** are present in the sdist with
exact frozen bytes. Both artifacts contain exactly the frozen 47 runtime
files. Their runtime tree SHA-256 is
`e4a399d9ea6cd487b399f2be7123c24e4b2319f6f596a7df5ef18632365988f9`, identical
to the earlier `89bd349` runtime. The verifier rejects duplicate archive members
and additional runtime files before accepting the normal byte comparisons.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.4.0a1-py3-none-any.whl` | 240827 | `5f335422619ee7361a9c4ddb9e0dc99dd548fda0764cfb769e7a8a6384259270` |
| `uta_reference_exchange-0.4.0a1.tar.gz` | 19211245 | `eccf90fc8b07b1fe17a25170332b1b846f06b2dee9e86f98027cf4b5e1ce97aa` |

The wheel was installed with `--no-deps --no-index` into a new external venv.
The frozen verifier ran under `python -I` with `PYTHONPATH` unset. All **eight
actual installed CLI/protocol tests passed in 7.678 seconds**, with no failures,
errors or skips. All eight recorded console commands also exited zero:
`uta-durable --help/init/inspect/status`, `uta-ops --help`, and
`uta demo/acceptance/scenario`. The seven original CLI tests and the independent
synthetic order/restart/cancellation protocol used installed financial modules
and real subprocesses, TLS, HMAC and SQLite. No financial function was patched.

The sdist was unpacked into a fresh directory without `.git`. Seven real legacy
writer-fence tests, the one archived managed-benchmark/profile test, and four
archive-verifier tests all passed there, with zero skips. The archived benchmark
test validates its historical data and preserves its original failure/limits;
it is not a new successful load test. The archive tests exercise healthy and
missing tracked sources, changed bytes, dirty tracked source, duplicate ZIP/tar
members and extra runtime members.

One additional actual negative control removes exactly
`evidence/runs/sqlite-fixture-resourcewarning/allocation-probe.py` from a copy of
this complete final sdist. The complete-source verifier exits 1 and reports
exactly that missing member. The original and deliberately incomplete archive
hashes, actual argv/cwd, report and raw stdout/stderr are retained. This confirms
the primary gate detects the omission that the earlier narrow gate missed.

`artifact-manifest.json`, `installed-report.json`, `package-verdict.json` and all
raw logs are retained here; exact repeatable commands are in `commands.txt`.
The verifier scripts come from the same frozen commit. These report files are
created after the frozen build and are not claimed to be members of that sdist.
The earlier `89bd349` and `28493d4` incomplete artifacts and red records remain
unchanged.

This is local Python 3.12 package acceptance. The integration gate owns the
separate full repository Python matrix. No systemd unit was installed or
started, and no public listener, HA/cross-AZ, 10,000/s, long-duration capacity,
custody or real-funds launch qualification is established here.
`production_approved` remains false. Artifact binaries remain in the external
artifact directory; no authority/auth database, TLS private key or signing
profile is committed.
