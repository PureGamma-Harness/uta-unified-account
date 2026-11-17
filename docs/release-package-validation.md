# Independent release package validation

The current frozen candidate `763202df9cb3ce089721e5281371aff3eab58089` passes a
new complete package exercise. Its sdist contains all **1475 tracked files**
with exact bytes, including the original historical CI ZIP. Both archives have
the dynamic **49 Python files plus dashboard**, with runtime tree SHA-256
`f57e7124063f35ff996132d4d1fc893fae39c8b67d27aa52458c20b1859d631e`.
A new venv actually passes isolated CLI/protocol **8/8**, view smoke **3/3**, all
eight console commands and no-`.git` sdist checks **7/1/4**, with no skips.
Helpers and copied hashes are recomputed from this exact source.

The [763202d artifact hashes and raw evidence](../evidence/20261117-package-763202d/README.md)
and [exact commands](../evidence/20261117-package-763202d/commands.txt) retain the
new runs. The tracked ZIP is byte-identical in source, sdist and unpacked source;
its recorded PR-merge SHA and failed historical CI result remain unchanged.
Two actual runtime-omission controls and a ZIP-only omission control each make
the primary gate exit 1. The ZIP-only control preserves both runtime maps and
fails the all-tracked-source gate. Byte identity with `7ae94eb` is independently
checked and supplies no borrowed functional PASS. Full matrix/CI qualification
belongs to the integration gate. This package exercise runs no six-hour or
pressure load and changes no production/HA/real-funds scope;
`production_approved` remains false.

The earlier frozen candidate `4608ffeda0651f8dafd2cd151618a71ed99aa62e` passes
new independent package acceptance: all **1258 tracked files** at that commit
are exact in the sdist, and both artifacts contain the dynamic **50 runtime
files**, including `failure_diagnostics.py`. A new venv passes the actual
isolated **8/8** CLI/protocol cases, all eight console commands and **3/3** frozen
read-view smoke cases. The no-`.git` sdist passes its 7 legacy, 1 historical
profile and 4 archive-verifier cases. Actual copies of the new wheel and sdist
with the diagnostic module omitted each make the primary gate exit 1.

The [4608ffe evidence and artifact hashes](../evidence/20261117-package-4608ffe/README.md)
and [exact commands](../evidence/20261117-package-4608ffe/commands.txt) bind this
result to that source and a freshly built/installed runtime. Earlier 13e results
and intermediate full-suite failures remain unchanged. The integration gate
owns the separate full runtime matrix and diagnostic/corrupt-inbox regression
validation. This package exercise runs no six-hour or capacity workload and
changes no production/HA/real-funds scope; `production_approved` remains false.

The earlier frozen candidate `13e6924377f031bb3da7ec94aa88df25ed7612ec` passes
fresh independent package acceptance. Its sdist contains all **1171 tracked
files at that commit** with exact bytes, and both artifacts contain the dynamic
**49 runtime files**, including the added startup protocol and read projections.
The runtime tree differs from the earlier 47-file candidate; no previous
functional result is reused. A new venv passes the actual isolated 8/8 CLI/
protocol tests and all eight recorded console commands. Three unchanged frozen
view cases also pass against installed modules, and the unpacked sdist passes
the 7 legacy, 1 historical-profile and 4 archive checks without `.git`.

The [current source/artifact evidence](../evidence/20261117-package-13e6924/README.md)
records both artifact hashes, dynamic runtime identity, exact commands and raw
logs, including the initial zero-test view-harness selection error. Actual new
artifact controls omitting `startup.py` or `durable_views.py` fail the primary
gate. The view smoke includes constructor tripwires and localhost HTTP HMAC;
its separate fixture/nonce writes and transport limits are explicit. CLI TLS
acceptance is recorded independently. This package exercise runs no six-hour
recovery test or capacity load, and does not change production/HA/real-funds
scope. The integration gate owns the separate full runtime matrix.
`production_approved` remains false.

The earlier frozen candidate `7200097ce9f92fa678907bee9a99933f60d65bc3` passes complete
source/archive and fresh installed-wheel acceptance. Its sdist contains all
862 tracked source/evidence files with exact bytes; both artifacts contain the
same 47 frozen runtime files. The isolated installed exercise passes 8/8 tests
and all eight recorded console commands. The unpacked sdist also passes seven
legacy-writer tests, one archived-profile test and four verifier tests without
an enclosing `.git`. An actual final-sdist control with the allocation probe
removed exits 1 for precisely that omission.

The [current evidence and artifact hashes](../evidence/20261117-package-7200097/README.md)
and [exact commands](../evidence/20261117-package-7200097/commands.txt) bind this
result to that Git commit and the independently built wheel/sdist. This is a
local Python 3.12 package gate; the integration gate owns the full Python matrix.
Production and real-funds launch approval remain false. Historical incomplete
packages below retain their original failed verdicts.

The earlier intermediate candidate
`28493d4f1ca78b8452a1e337e2cd5277a81d95a5` also passed a fresh installed 8/8
exercise, but a complete tracked-source inventory found four omitted sdist
members. Its aggregate package verdict remains failed. The
[intermediate evidence](../evidence/20261117-package-28493d4/README.md) preserves
the original narrower green check, the strengthened red check, and an actual
missing-probe negative control. A revised manifest and complete-source verifier
are statically checked; they require a new frozen build before qualification.

The frozen `0.4.0a1` candidate at
`89bd349429db3207b61caf1bf2212f6a96c4b76c` passed installation and functional
checks, but **its source distribution is incomplete**: it omits
`formal/results/shard-admission-model-20261115.json`. The release packaging gate
remains open for that artifact. The failed artifact and its original evidence
are retained; a corrected source distribution must receive a separate manifest.
Real-funds production remains **NO-GO**.

## Frozen source and artifacts

The build used a `git archive` copy outside the repository, without `.git`.
It did not edit the frozen runtime. Direct `setuptools.build_meta` calls built
the wheel and sdist with Python 3.12.14, setuptools 84.2.1 and wheel 0.48.0;
the optional `build` frontend was unavailable. No dependency download or
dependency installation was needed. These are exact artifact hashes for this
build; byte-reproducible rebuilding across different timestamps is not claimed.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.4.0a1-py3-none-any.whl` | 240040 | `3f092e6d88bf427af00e94679cd71be70fe61219536c8aaaf827244c03b1e16e` |
| `uta_reference_exchange-0.4.0a1.tar.gz` | 18340701 | `426cb722c276af283795395008a02fd6ba5cf04e0e893ab34989d1ab74705e8e` |

The package version, exact Git commit and runtime source digest are associated
in the archived manifest. Version metadata alone does not identify a Git commit.
All **47 runtime files** (`uta/*.py` and `dashboard.html`) have identical source,
wheel and sdist SHA-256 values. The runtime-tree digest is
`e4a399d9ea6cd487b399f2be7123c24e4b2319f6f596a7df5ef18632365988f9`;
it hashes compact, sorted JSON mapping each runtime path to its SHA-256.

The sdist inventory checks every frozen tracked file under `formal`, `tools`
and `tests`, plus all benchmark `.prof` and `.prof.gz` files: **134 required
paths**, exactly one missing. The three uncompressed managed benchmark profiles
are present and byte-identical. The historical source fixture is pinned to
`ad3f5b894f96ed6857a061b71290047ae1d4d0e7`, has archive SHA-256
`af1ffcbdb78d4f2c789f049cb4f3c61e75724a10a1f8f55d0d1ed09af1cda265`,
and includes its original LICENSE. It does not depend on local Git history.

## Installed wheel checks

A new external virtual environment installed the wheel using
`pip install --no-deps --no-index`. The verifier ran from an external directory
with `python -I`, no `PYTHONPATH`, and assertions that **every imported `uta`
module came from that virtual environment's site-packages**. The unchanged
frozen `tests/test_durable_cli.py` was copied outside the repository. Its only
override was the test helper's `ROOT`, used for subprocess working directories,
to installed site-packages. No financial function or original assertion was
patched. Spawned workers and `python -m uta.durable_cli` used installed modules.

All **seven original CLI tests plus one independent protocol test passed**,
with no skips. This includes real verified TLS, HMAC authentication, rejected
Bearer fallback, replay rejection after restart, private-file permissions,
failed binding without worker startup, explicit audit upgrade, and persisted
pending commands under a new coordinator PID and owner generation.

The additional test used authorized synthetic offline funding. A real TLS order
request's response was discarded without reading it; the durable terminal was
observed independently. An identical command with a new request nonce after
coordinator restart returned the same successful result. There was exactly one
order, one acceptance decision, and the independently expected **10.04 USD**
reservation. A cancellation durably queued while workers were stopped remained
`PENDING` until the new worker executed it, then became `SUCCEEDED`. The one
order became `CANCELLED`; cash remained 1000 USD. `durably_queued` was never
counted as financial acceptance.

The first version of this extra test queried a nonexistent database column
`reserved_margin`; the product stores this calculated value in the terminal
receipt, not an order-table column. That **test fixture error** and the failed
8-test run are retained. The corrected verifier checks the persistent terminal
receipt and raw order rows against the same financial expectations. The second
run passed 8/8 in 7.966 seconds. No runtime change was made to obtain the pass.

Actual installed console commands also passed: `uta-durable --help`, `init`,
`inspect`, `status`, `uta-ops --help`, and `uta demo`, `uta acceptance`, `uta scenario`. Functional
acceptance included classic import, borrowing and repayment, two real spot
matches, three linear matches, partial liquidation, restart, and read-only
four-side reconciliation. Terminal balances were **93.152 USD and 0.999 BTC**;
there were six paired linear fills and zero unpaired fills. The research
scenario retained its reported insolvent ending state and verified seven replay
events; running that example does not imply risk recovery or product approval.

Separately, the sdist was unpacked into a directory without `.git`. All **seven
legacy-writer fixture tests** and the **one archived managed benchmark test**
passed. The latter independently verifies profile/arrival manifest hashes,
including the raw `.prof` files. Its historical results remain 200 queue ACKs,
171 financial successes, 18 business rejections, 11 control/market rejections,
and a preserved `SQLITE_IOERR_SHORT_READ`; this packaging check does not
reinterpret that run as a successful capacity gate.

An additional read-only review identified limits in the first verifier scripts,
without finding incorrect runtime bytes or source imports in the recorded run.
The follow-up binds installed files to the complete artifact manifest and Git
commit, pins the copied CLI helper SHA before executing it, requires isolated
Python plus exactly eight tests with zero skips, checks all three console-script
targets, and rejects extra sdist runtime files or dirty tracked verification
sources. The repeated financial response must equal the original complete
terminal result. The strengthened run passed **8/8 in 7.608 seconds**. Its
separate bound manifest and report are retained alongside the unchanged earlier
raw records.

Six actual negative controls failed as required: an additional sdist runtime
file, wrong installed-runtime digest, dirty tracked formal source, incorrect
console-script target, modified CLI test helper and nonisolated invocation.
These validate the verifier's rejection paths; they do not represent failures
of the unmodified wheel. `--identity-only` checks installed byte identity and
explicitly reports zero functional tests, for a later artifact whose runtime
bytes have already passed the full installed exercise.

## Reproduce historical 89bd349 check

Keep the verifier scripts from this report commit outside the frozen checkout.
Create a fresh checkout at the stated Git commit. Use separate build, venv,
output and extraction directories; never initialize an existing financial
authority during a package check. The original exact command forms and outputs
are in [the evidence directory](../evidence/20261117-package-89bd349/commands.txt).

```sh
git -C "$FROZEN_CHECKOUT" archive --format=tar --output="$WORK/source.tar" HEAD
tar -xf "$WORK/source.tar" -C "$WORK/build-source"
# Run in $WORK/build-source, using a Python with setuptools>=68 and wheel:
python -c 'import setuptools.build_meta as b; b.build_wheel("../artifacts"); b.build_sdist("../artifacts")'
python "$VERIFIERS/verify_release_archives.py" --source "$FROZEN_CHECKOUT" \
  --commit 89bd349 --wheel "$WHEEL" --sdist "$SDIST" --output "$WORK/manifest.json"
python -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --no-deps --no-index "$WHEEL"
env -u PYTHONPATH "$WORK/venv/bin/python" -I \
  "$VERIFIERS/validate_installed_release.py" --source "$FROZEN_CHECKOUT" \
  --artifact-manifest "$WORK/manifest.json" \
  --output "$WORK/installed"
```

The archive verifier intentionally exits 1 for this original incomplete sdist.
The installed verifier exits 0 only when all original and additional tests pass.
Its temporary authority, nonce store, TLS key and signing profile are outside
the repository; no databases or generated secret material are committed.

## Boundaries and deployment rollback

This is one Python 3.12 local installation check, using real child processes,
SQLite, TLS and synthetic accounts. The separately run full Python matrix is
owned by the integration gate and is not attributed to this package exercise.
No systemd unit was installed or started. No public listener, external custody,
real funds, cross-AZ replication, 10,000/s or 30-minute capacity qualification,
24-hour completion, or financial-owner launch approval is established here.

For a deployment, pin the reviewed wheel hash and retain the matching source
distribution, runtime manifest and audit artifacts. Halt ingress, stop the
coordinator and prove that child writers have exited or been fenced before
switching a virtual environment. Preserve original command IDs and query
durable outcomes after restart. Never downgrade required-audit databases to a
binary lacking schema/capability support; never delete inbox, fence, nonce or
audit records to make a rollback start. Use the existing offline recovery and
reconciliation procedures when an authority has advanced. The unit templates
and operational rollback procedure still require deployment-environment
validation and explicit real-funds launch approval.
