# Independent package acceptance: 4608ffe

Exact frozen source: `4608ffeda0651f8dafd2cd151618a71ed99aa62e` at
`/workspace/uta-operations-freeze-4608ffe`, kept unchanged and clean.
Independent report worktree: `/workspace/uta-package-4608ffe`.
New external build/install: `/tmp/uta-release-4608ffe-QxAxe9`.

The actual new artifacts pass the package checks. The sdist contains all
**1258 tracked files at this frozen commit** with exact bytes. Both archives
contain exactly the frozen **50 runtime files**, with tree SHA-256
`857382fbc0a6faee37006f85e87305ebc0ed3f40288e4db8593450de8f23c724`.
Compared with `13e6924`, `uta/failure_diagnostics.py` is added and
`uta/durable_commands.py` / `uta/durable_process.py` change. The comparison is
byte evidence only; no earlier functional pass is reused.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.4.0a1-py3-none-any.whl` | 260671 | `93c4ca716f11732829d421a751cfc61f3dfd500184984e0344e04615349cde35` |
| `uta_reference_exchange-0.4.0a1.tar.gz` | 21422284 | `d523cc27319118f2fe8dd1eccf5308f6bf9dc478fa7cfb65d7b7ad42061f4275` |

A clean Git archive is built in an external directory without `.git`, then the
wheel is installed with `--no-deps --no-index` into a new venv. Under isolated
Python with `PYTHONPATH` unset, all **eight actual installed CLI/protocol tests
pass in 9.286s**, without failures, errors or skips. All eight recorded console
commands exit zero: durable help/init/inspect/status, ops help, demo, functional
acceptance and scenario. The original lifecycle tests exercise real child
processes, TLS, HMAC, SQLite and restart using synthetic accounts. The installed
module records resolve the new `failure_diagnostics.py` and startup module to
this venv, not a source checkout.

The generic read-view smoke verifier is taken from the same frozen commit,
although its repository path retains an earlier report-directory name. It binds
the new source HEAD, Git helper bytes, new artifact hashes and all 50 installed
runtime files. It does not read the earlier report's PASS. A new invocation and
output directory pass **3/3 unchanged frozen view cases in 0.453s**: all account
resources, HMAC account scope, and two-shard routing over actual HTTP. The view
module also resolves inside the fresh venv.

These view tests create synthetic financial fixtures before reading and use
constructor-raising tripwires during reads. Their financial snapshots remain
unchanged. The HMAC view test uses localhost HTTP with `require_tls=False` and
writes its separate authentication nonce database. The separate CLI suite
provides the recorded TLS lifecycle evidence; the view smoke does not claim TLS
coverage or an absence of fixture/auth writes.

The unpacked sdist has no enclosing `.git`. All seven real legacy writer-fence
tests, the one historical managed-probe/profile check and four archive-verifier
tests pass with zero skips. The historical profile check retains its original
limits and failures; it is not a new load run. Build, installation and functional
checks run on one allowed CPU.

Two actual negative controls independently copy these complete artifacts and
omit exactly `uta/failure_diagnostics.py` from the wheel or sdist. Both invoke
the same frozen primary archive verifier and actually exit 1 for the expected
dynamic runtime mismatch. The sdist additionally lists exactly that missing
tracked file. The independent archives are never installed and execute no
financial test. The tested reproducible control script, exact argv/cwd, hashes,
reports and raw stdout/stderr are retained.

`artifact-manifest.json`, both installed reports, `installed-new-module-evidence.json`,
`package-verdict.json`, source/verifier hashes and all raw logs bind these checks
to the exact source and artifacts. `commands.txt` gives repeatable commands.
The report is created after the frozen build and is not claimed to be inside
that sdist. The earlier `13e6924` package records, original red records and
intermediate full-suite failures remain unchanged; package success does not
retroactively change their results. No runtime, ordinary test or manifest rule
is changed by this review.

This is local Python 3.12 package acceptance. The integration gate owns the
separate 1096-test runtime matrix and diagnostic/corrupt-inbox regression work;
those results are not attributed to this package exercise. No six-hour run,
benchmark, systemd deployment, public listener, sustained capacity, HA, custody
or real-funds qualification is established here. Production scope is unchanged:
`production_approved=false`. Binaries remain in the external artifact directory;
authority/auth databases, signing profiles and TLS private keys are not committed.
