# Actual fresh package acceptance: d421df3

**PASS for package scope only.** Frozen source is
`d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6` at
`/workspace/uta-observer-freeze-d421df3`, clean before and after all checks.
This separate evidence commit is not part of that frozen source's 2753 files.
No prior package functional PASS is reused, and bb34's original full QA/CI
**NO_GO** remains unchanged. Complete new local QA/CI and long-run outcomes
are outside this report. Production, real-funds, HA and 10,000/s capacity
approval remain false.
Integration subsequently reports new d421 CI at six PASS and two failed jobs,
so the candidate remains **NO_GO** outside this package scope. Those CI raw
artifacts are retained by integration; this package exercise does not rerun or
reclassify them.

## Exact new artifacts and tests

The original binaries and private fixture directories remain outside Git at
`/tmp/uta-release-d421df3-yy2hmth8`. Nothing from the old bb34 package directory
was rebuilt, overwritten or installed. The source was copied with actual
`git archive`, without `.git`, and built via the installed stdlib/setuptools
build backend. No dependency download was needed. Build warnings remain in
the unmodified raw stderr. Byte-reproducible rebuilding across timestamps is
not claimed.

| New artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 279432 | `8fa7255d46075b8c14fc004994f219a9109569abedb50894f5678d603ac6abd1` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 30530638 | `61ad6c286bdaaf33f23d9fb65a22483419f6594f956cfc9b46b5552b7620e300` |

All **2753 tracked files** match frozen source bytes in the sdist, which has
2760 regular members including generated metadata. The dynamic **52 runtime
files** match source/wheel/sdist and actual installed bytes. Their compact
sorted JSON map hashes to
`e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792`.
`source-proof.json` has every tracked SHA and the actual frozen Git archive
identity. `runtime-comparison-bb34b5f.json` recomputes original bb34 Git blobs;
runtime byte equality supplies no borrowed test result.

| Actual new check | Tests/commands | Result |
| --- | ---: | --- |
| Frozen primary archive gate | all seven checks | PASS |
| Fresh venv, `python -I`, unchanged frozen CLI helper plus protocol case | 8 | PASS, no skips |
| Actual installed console commands | 8 | exit 0 each |
| Fresh installed read views, unchanged copied helper | 3 | PASS, no skips |
| Unpacked sdist without `.git`, legacy writer checks | 7 | PASS |
| Unpacked sdist archived-profile check | 1 | PASS |
| Unpacked sdist release-verifier checks | 19 | PASS |
| Actual runtime omission controls | 2 | expected primary exit 1 |
| Actual tracked historical ZIP omission controls | 8 | expected primary exit 1 |
| Independent actual-byte/report-binding review of all controls | 10 | PASS |

Installed source/module locations, copied helper SHA, source/artifact identity,
interpreter isolation, test counters and eight actual commands are recorded
under `installed/` and `installed-views/`. The helper's ROOT override changes
only subprocess cwd to installed site-packages. No financial implementation,
assertion or installed runtime is patched. The tests use fresh private synthetic
authorities, localhost transport and actual TLS/HMAC where the frozen helpers
require them. View transport limitations and nonce writes remain explicit in
its original report. No live/external service was accessed.

## Complete negative-control matrix

The existing frozen collectors are unchanged. The new
`verify_control_bindings.py` is an independent report-only inspection, not a
replacement collector or primary gate. It reads actual archives and reports;
it executes no tests, services or SQL. Its actual successful output is
`strict-control-bindings.json`. Every negative report binds actual SHA **and
bytes** for its negative input and the untouched other positive package.

| Primary check | Positive | Wheel runtime omitted | Sdist runtime omitted | Each one-ZIP sdist omission |
| --- | --- | --- | --- | --- |
| `version` | true | true | true | true |
| `wheel_runtime_exact` | true | **false** | true | true |
| `sdist_runtime_exact` | true | true | **false** | true |
| `sdist_required_files_exact` | true | true | **false** | **false** |
| `legacy_fixture_pinned` | true | true | true | true |
| `legacy_fixture_licensed` | true | true | true | true |
| `entry_points` | true | true | true | true |

Each case requires exactly this seven-key set and false set, actual primary
exit 1, a false aggregate result, unchanged frozen runtime map/tree and no
mismatched source bytes. Wheel omission leaves the sdist missing list empty;
sdist cases have exactly the target in that list. The runtime target is
`uta/failure_diagnostics.py`. Each actual negative ZIP/tar index differs from
the actual positive index only by deletion of the target. All remaining
member data and stable attributes are exact, including unchanged wheel RECORD;
physical archive offsets are excluded because deletion shifts them. Negative
archives were never installed. Actual positive originals remain unchanged.

`tracked-ci-zip-checks/tracked-ci-zips.json` records all eight targets and their
individual actual gate executions. The ordered targets are:

1. `evidence/reviews/observer-py310-fixture/ci-originals/pull_request-python310/original-ci-artifact.zip`
2. `evidence/reviews/observer-py310-fixture/ci-originals/push-python310/original-ci-artifact.zip`
3. `evidence/runs/a35-startup-phase/original-ci-artifact.zip`
4. `evidence/runs/capacity-qa-a35fd56/ci/44066483487/uta-unit-validation-python-3.13/original-ci-artifact.zip`
5. `evidence/runs/capacity-qa-a35fd56/ci/44066492849/uta-unit-validation-python-3.12/original-ci-artifact.zip`
6. `evidence/runs/ci-4e-view-phase/original-ci-artifact.zip`
7. `evidence/runs/ci-a35-gateway-readiness/original-push-python313/original-ci-artifact.zip`
8. `evidence/runs/startup-producer-fixture/original-ci/artifact.zip`

Every original ZIP is byte-exact in frozen source, positive sdist and unpacked
source. Its three original members, log SHA, worker summary, unchanged source
map and corresponding historical Git blobs are verified. Provenance for the
old six is retained from the original explicit map. The two added Python 3.10
artifacts use bb34 as `reference_commit`; their reported `code_commit` remains
respectively PR merge `ff279680ef869954c1ddbfad81a82562190d9c06` and push
`bb34b5fb4397f485c04fe440557b24bb28d1cae2`. Both original 1411-test/one-ERROR
outcomes remain failures. Historical CI never qualifies current d421.

## Reproduction, errors and public boundary

`execution-driver.py` is the exact actually executed standard driver adapted
to the new SHA/directories. `raw/execution.json` and `raw/commands.txt` retain
the 15 actual core runs, argv, explicit cwd, exit, UTC times and durations.
`tracked-zip-execution.json` records the separate eight-ZIP archive-only phase.
All execution inherits CPU2 affinity on a shared host; no exclusive CPU/cpuset
claim is made. The longest functional command is 10.567 s; its eight tests take
9.042 s. The archive-only eight-case collector takes 70.492 s in aggregate and
runs no financial workload. There is no pressure or long-run measurement.

The first independent reporter reached the first tar index digest, then raised
`TypeError` when JSON-hashing tar's bytes-valued type field. Its exact
script and original raw error remain under `strict-first-attempt/`. The final
script encodes that stable field as hex and rechecks all inputs read-only.
No failed artifact/checker output was replaced and no release binary changed.

To reproduce the successful independent review without building/installing:

```sh
taskset -c 2 python evidence/20261117-package-d421df3/verify_control_bindings.py \
  --source /workspace/uta-observer-freeze-d421df3 \
  --work /tmp/uta-release-d421df3-yy2hmth8 \
  --records /workspace/uta-package-d421df3 \
  --provenance /workspace/uta-package-d421df3/ci-zip-provenance.json \
  --output /tmp/d421-independent-review/strict-control-bindings.json
```

Create the fresh output parent first. Original artifact paths must remain
available. To rerun the full exercise, choose new external work/report paths
and adapt the archived driver's path constants and work-locator file; its
`exist_ok=False` guards deliberately reject reuse. Keep the exact frozen SHA.
The original provenance map/collector and successful strict command are
recorded separately; do not install any negative artifact.

`collect_public.py` copied an explicit allowlist byte-for-byte; all origins,
bytes and SHA values are in `public-allowlist.json`. Only safe JSON, text and
Python drivers/reports are published. Release/negative package binaries,
original CI ZIP binaries, private auth/TLS files, financial DBs and signed URLs
stay external. This directory contains no copied private fixture tree.
`package-verdict.json` contains the machine-readable scope boundaries. See
[deployment and rollback](../../docs/release-package-d421df3.md#deployment-and-rollback).
