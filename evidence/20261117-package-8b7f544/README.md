# Fresh package acceptance: 8b7f544

**PASS for package scope only.** Exact frozen source is
`8b7f544fcbdfd540d43de1d6560022c6ebbd3799`, clean at
`/workspace/uta-observer-freeze-8b7f544`. This subsequent docs/evidence commit
is not part of the frozen 3355-file source. Complete local QA/CI remains a
separate gate; this exercise grants no pressure, smoke, long-run, capacity, HA,
Native V2, production or real-funds qualification. Historical bb34 and d421
NO_GO results, original artifacts and raw logs remain unchanged.

## Exact artifacts and new executions

The fresh external work directory is `/tmp/uta-release-8b7f544-r6v0zf_q`.
Actual positive/negative package binaries and private fixtures stay there.
No previous binary or installed environment is reused. The build uses a new
`git archive` copy without `.git` and installed setuptools/wheel, with no
dependency download. Source, wheel/sdist, installation and copied helpers are
bound by their actual hashes. Rebuilding across timestamps is not claimed to
produce identical compressed bytes.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 279432 | `6265062de210164df3d9b4ab1a6a73bffab6fea99a40e27e7c98bc05644e10f0` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 32396269 | `727eebc73972b2d2fc69a67ca38e58576c42c2e788a07b3dab8865a00f5429e0` |

All **3355 tracked source/evidence files** are exact in the sdist. The dynamic
**52 runtime Python/HTML files** match source, both artifacts and actual
installed site-packages. Runtime-tree SHA-256 is
`e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792`.
`source-proof.json` gives every tracked file hash and original Git archive
identity. `runtime-comparison-d421df3.json` actually recomputes d421 Git blobs
and confirms identical runtime bytes; no functional result is borrowed.

| Actual fresh check | Count | Result |
| --- | ---: | --- |
| Primary archive gate | complete seven checks | PASS |
| New venv `python -I`, CLI/protocol | 8 | PASS, no skips |
| Installed console commands | 8 | exit 0 each |
| Installed read-view tests | 3 | PASS, no skips |
| No-`.git` sdist legacy writer tests | 7 | PASS |
| No-`.git` sdist archived-profile test | 1 | PASS |
| No-`.git` sdist release-verifier tests | 19 | PASS |
| Actual runtime omission primary executions | 2 | expected exit 1 each |
| Actual tracked CI ZIP omission primary executions | 10 | expected exit 1 each |
| Independent artifact/report/member comparison | 12 | PASS |

The unchanged frozen helper bytes, module locations, isolated interpreter,
cleared PYTHONPATH, counters and commands are recorded in `installed/` and
`installed-views/`. Only helper subprocess cwd is redirected to installed
site-packages. No financial implementation or original assertion is patched.
Fixtures are fresh private synthetic authorities. The original helper reports
retain actual TLS/HMAC coverage and the separate view-test localhost HTTP and
nonce-write limits. No external service or old job SQL is accessed.

## Complete omission matrix and provenance

| Primary check | Positive | Wheel runtime omission | Sdist runtime omission | Each single-ZIP sdist omission |
| --- | --- | --- | --- | --- |
| `version` | true | true | true | true |
| `wheel_runtime_exact` | true | **false** | true | true |
| `sdist_runtime_exact` | true | true | **false** | true |
| `sdist_required_files_exact` | true | true | **false** | **false** |
| `legacy_fixture_pinned` | true | true | true | true |
| `legacy_fixture_licensed` | true | true | true | true |
| `entry_points` | true | true | true | true |

The runtime target is `uta/failure_diagnostics.py`. Each negative has exactly
the seven check keys above and the stated false set; no unrelated false or
missing check is accepted. Sdist cases have only their target in `sdist_missing`
and no mismatched bytes; the wheel case leaves that list empty. Every report
binds the actual negative SHA **and size**, unchanged other positive package,
frozen source/runtime map/tree, version/helper identity and actual primary
stdout/exit 1. The separate report-only checker verifies a pure target deletion:
no added/changed members, identical remaining bytes and stable member metadata,
and identical member order with only the target removed. It also preserves
the wheel archive comment and unchanged RECORD. Physical offsets necessarily
shift and are excluded. Negative binaries were never installed.

The original frozen collectors are not changed or declared fixed. The new
`verify_control_bindings.py` reads the actual positive and negative files; it
executes no service, test, financial import or SQL. Its complete successful
inspection is `strict-control-bindings.json`, with exact report/input identities
and the pure-member differences for all twelve controls. There is no failed
first attempt for this new checker run; prior d421 reporting errors remain in
the original historical evidence.

`tracked-ci-zip-checks/tracked-ci-zips.json` records all ten sorted targets and
individual real omission executions. `ci-zip-provenance.json` has exactly one
explicit historical registration per tracked ZIP. Each original ZIP is exact
between source, positive sdist and unpacked source. Its three original members,
unittest log hash, worker counters, unchanged source map and matching original
Git inputs are verified. The old eight registrations remain unchanged. Added
registrations are:

| Tracked historical artifact | Reference commit | Original reported code commit | Original result preserved |
| --- | --- | --- | --- |
| `evidence/reviews/readiness-d421-fixture/ci-originals/pull_request-python313/original-ci-artifact.zip` | `d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6` | `7114617951b6b4e4313c19439f853fdd115e35d0` | 1413 tests, 2 failures |
| `evidence/reviews/readiness-d421-fixture/ci-originals/push-python311/original-ci-artifact.zip` | `d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6` | `d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6` | 1413 tests, 1 error |

Those merge/push identifiers and failed historical outcomes are not relabeled
as the current source or current CI success.

## Execution, space and public boundary

`execution-driver.py` is the actually executed standard driver adapted to this
SHA and new paths. `raw/execution.json` records 15 core commands with explicit
cwd, actual exits, UTC times and monotonic durations. `run_followup.py` records
the separate ZIP and strict phases in `tracked-zip-execution.json` and
`strict-execution.json`, including actual helper SHA, UTC and monotonic clocks.
`clocks.json` and `environment.json` retain clock implementations and build
environment. All execution uses CPU2 affinity on a shared host, without an
exclusive CPU/cpuset claim.

The longest functional command is 11.402 s; its eight tests take 9.994 s.
Views take 0.704 s. Legacy/profile/release suites take 0.855/0.006/4.560 s.
The ten-case archive-only collector takes 105.058 s in aggregate and the
read-only twelve-case inspection takes 13.525 s. Neither runs financial load.
Original build/extraction deprecation warnings remain in raw stderr.

Before this build the observed free space was 22,103,818,240 bytes. After fresh
positive and negative artifacts it was **21,126,705,152 bytes**, which is
616,566,784 bytes below the nominal 20.25 GiB proposal margin. The exact
`df -B1` output/time and limits are in `initial-filesystem.json` and
`final-filesystem.json`. Shared free space is not reserved. No old build tree,
unpacked source, venv, original package or job was deleted. Integration must
independently remeasure after any authorized cleanup and before long-run
preflight; this package PASS cannot approve storage prerequisites or a long run.

The public collector uses an explicit text/JSON/Python allowlist and screens
private material. `public-allowlist.json` binds copied original paths, bytes and
SHA; `evidence-manifest.json` hashes the published files. No release/negative
archive binaries, new CI ZIP binaries, authentication/TLS assets, financial DBs
or signed URLs are copied. Historical binaries already in frozen source are
not republished in this new evidence directory.

To reproduce only the independent read-only check, create a fresh output parent
and run the published checker with `--source /workspace/uta-observer-freeze-8b7f544`,
`--work /tmp/uta-release-8b7f544-r6v0zf_q`, `--records /workspace/uta-package-8b7f544`,
`--provenance /workspace/uta-package-8b7f544/ci-zip-provenance.json` and a fresh
`--output` path, under `taskset -c 2 python`. It requires the original external
artifacts. Full reruns require new work/report paths; the archived drivers
deliberately reject overwriting previous evidence. Exact original commands are
in the execution JSON and `raw/commands.txt`.

See [deployment and rollback](../../docs/release-package-8b7f544.md#deployment-and-rollback).
