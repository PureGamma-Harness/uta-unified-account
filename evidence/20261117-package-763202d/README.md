# Independent fresh package acceptance: 763202d

Exact frozen source: `763202df9cb3ce089721e5281371aff3eab58089` at
`/workspace/uta-operations-freeze-763202d`, unchanged and clean.
Independent report worktree: `/workspace/uta-package-763202d`.
New external build/install: `/tmp/uta-release-763202d-0AyiOQ`.

The newly built artifacts pass the complete package checks. All **1475 tracked
files at this commit** occur in the sdist with exact bytes. Both archives contain
exactly **49 Python runtime files plus the dashboard**, with runtime tree SHA-256
`f57e7124063f35ff996132d4d1fc893fae39c8b67d27aa52458c20b1859d631e`.
An independent Git-byte comparison confirms the runtime map equals
`7ae94eb8a783f8e134ac90c11a713df7bb02d5f1`; this comparison reuses no old
functional result. The source archive, artifacts, venv and every check output
directory are new for `763202d`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.4.0a1-py3-none-any.whl` | 261917 | `242595fea87e7afd10597c7e8e99111e9f58900109175f3a78b6272087eaa672` |
| `uta_reference_exchange-0.4.0a1.tar.gz` | 22640005 | `a5765f165a2edecbeee417965083435f3af738e10b462d04faf92e0668fe38c1` |

The source is exported by Git and built without `.git`. A new venv installs the
local wheel with `--no-index --no-deps`. With `python -I` and `PYTHONPATH` unset,
the actual installed lifecycle/protocol suite passes **8/8 in 9.360s**, and all
eight recorded console commands exit zero. The separately invoked installed
read-view smoke passes **3/3 in 0.533s**. There are zero failures, errors or skips
in these package runs. Both test helpers are freshly hashed from `763202d` and
their copied bytes are checked against that source before execution. No old
test hash or PASS report is substituted for these new runs.

The lifecycle suite uses real processes, verified TLS, HMAC, restart and SQLite
with explicitly synthetic accounts. Read-view setup also writes synthetic
fixtures. Its original read-phase assertions preserve financial snapshots and
use constructor-raising tripwires. The HMAC view case uses localhost HTTP with
`require_tls=False` and writes its separate nonce database. Its three view cases
do not claim TLS coverage; that evidence comes from the separate CLI suite.
Every loaded financial module resolves inside the new installed venv.

The unpacked sdist has no `.git`. Seven real legacy-writer fixture cases, one
archived managed-probe/profile case and four archive-verifier cases all pass,
with zero skips. The archived profile's original failure/limits remain intact;
this package check does not turn it into a new capacity run. Build and checks
use one allowed CPU. No pressure load or new long-run job is started.

## Original CI ZIP is actually shipped

The tracked file
`evidence/runs/startup-producer-fixture/original-ci/artifact.zip` is present in
the sdist and unpacked source, byte-identical to the frozen source. All three
copies have SHA-256
`097dd0d4e266d82a85404c32c9e9c6ec8ea19c7bd8817831b76a6c4b44893bdf`.
Its summary, unittest and worker-result members also equal the tracked raw
sibling files. The existing `evidence *.zip` manifest rule is exercised by this
actual build and the all-tracked-file primary verifier.

The original ZIP remains a **failed historical PR-merge CI record**:
`code_commit=bd8e5b452166477bb15adeb5807f2c1b98b782ab`, 1110 tests, zero failures,
one error, `passed=false`. Its before/after recorded source hashes independently
match the `7ae94eb` reference Git source. Its recorded merge SHA is preserved;
it is not relabelled as `763202d` HEAD or a new QA PASS. Packaging that evidence
does not requalify its failure. Only filtered provenance fields and member
digests are repeated in this report; no download metadata or signed URL is used.

Three actual negative controls copy the new positive artifacts: two omit
`uta/failure_diagnostics.py` from the wheel or sdist; the third omits only the
tracked CI ZIP from an sdist copy. The same frozen primary verifier actually
exits 1 for each expected omission. In the ZIP-only control both runtime maps
still match, while the all-tracked-source gate fails and names precisely the
missing ZIP. Negative archives are never installed and execute no financial
test. The exact control code, argv/cwd, digests, reports and raw output are kept.

`artifact-manifest.json`, both installed reports, `ci-zip-inclusion.json`,
`package-verdict.json`, environment/helper hashes and raw stdout/stderr bind the
new results to this source and these artifacts. Reproduction commands are in
`commands.txt`. These report files are written after the frozen build and are
not claimed as members of that sdist. Original packages and red/error records
remain unchanged. The report modifies no runtime, standard test, manifest rule,
frozen tree or live job.

This is local Python 3.12 package acceptance. The integration gate owns the
separate full-runtime and CI qualification; they are not inferred from this
package PASS. No six-hour run, benchmark, deployment, public listener, sustained
capacity, HA, custody or real-funds qualification is established here.
`production_approved` remains false. Binaries remain in the external artifact
directory; no authority/auth database, signing profile or TLS private key is
committed by this report.
