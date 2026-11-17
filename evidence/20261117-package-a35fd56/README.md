# Fresh 0.5.0a1 package acceptance — a35fd56

Frozen source: `a35fd56fc98126b3e5cced8a459bd04ca580e537` at
`/workspace/uta-capacity-freeze-a35fd56`. It remained clean and unchanged.
This report is in a separate worktree. Every artifact and functional result
below was newly produced; no 0.4 artifact or historical PASS was reused.

**The historical single-ZIP helper failed in this run.** Its actual exit1 and
full assertion traceback remain in `old-ci-zip-helper-actual.*.txt`. It assumes
one tracked ZIP; this frozen source has two. This is a historical auxiliary
script compatibility failure, not a failure of the primary archive gate.
The new report-tree `verify_tracked_ci_zips.py` and explicit provenance map
independently cover both ZIPs. Its code and actual execution are retained.
Do not describe the complete exercise as an all-green unchanged-helper run.

## Newly executed checks

- Fresh no-Git source from `git archive`, actual wheel and sdist build.
- Primary gate: all **1961 tracked files**, dynamic **51 runtime files**,
  source version `0.5.0a1`, entrypoints and legacy license/provenance exact.
- Fresh external venv installation of that exact local wheel, `--no-deps
  --no-index`. `python -I` with PYTHONPATH unset imported only installed
  financial modules and checked their complete runtime byte map.
- Installed lifecycle/TLS/protocol tests **8/8** (8.814s), eight actual console
  commands exit0; installed read-view smoke **3/3** (0.496s). The read-view
  HMAC test uses localhost HTTP as explicitly recorded; separate CLI tests
  cover TLS. No financial function or guard is replaced.
- Extracted new sdist has no `.git`: old-binary fixture tests **7/7** (0.605s),
  archived-profile assertion **1/1** (0.004s), current archive verifier tests
  **19/19** (3.990s). All have zero failures/errors/skips. Reading an archived
  profile is not a new profile or load run.
- Four actual omission controls, all primary-gate **exit1**: omit the runtime
  failure-diagnostics module separately from wheel and sdist; then omit each
  of the two tracked CI ZIPs separately from a new sdist copy. No negative
  artifact is installed. ZIP-only negatives retain exact wheel/runtime maps
  and fail only the all-tracked-source gate for the removed path.

The original ZIP recording 1110 tests/1 error/pass=false retains merge
`bd8e5b452166477bb15adeb5807f2c1b98b782ab` and its 208 input hashes match
reference source `7ae94eb8a783f8e134ac90c11a713df7bb02d5f1`. The second ZIP
records 1168 tests/1 failure/pass=false at merge
`1702398f52970ac7b29619c46ad11b2a9f6909c2`; its 217 input hashes match
`4e59084544b8816e6e50e4caea7c6f60cff43a00`. Those PR merge identifiers and
source references are distinct and preserved. Neither historical failure is
relabelled as the current release's QA result.

## Evidence and reproduction

`execution.json` has each actual argv, cwd, UTC start/end, return code and
elapsed time; `commands.txt` is the readable command record. Stage stdout and
stderr are complete. `package_runner.py.txt` is the original driver.
`artifact-manifest.json`, installed reports, omission reports, helper hashes,
provenance and the outer manifest bind the chain to the frozen Git bytes.
The outer driver recomputed positive wheel/sdist hashes after all controls.
Only whitelisted reports/logs are archived: no nonce/auth/authority database,
TLS private key, signing profile, venv or binary artifact is published here.
Actual artifacts and private synthetic databases remain under
`/tmp/uta-release-a35fd56-gfjdl4l_`.

For reproduction choose new empty build/venv/external/output directories,
archive the stated frozen commit, build without `.git`, and use the commands
with those new paths. Run the current frozen primary/installed helpers.
For ZIPs use this report's generic helper and provenance JSON; retain the
original single-ZIP failure when reproducing the historical helper. Never
modify frozen source or an active authority to make a check pass.

The actual processes were bound to **CPU2**; matrix CPU1 and the continuing
stability job CPU0 were coordinated on the same host. This is process affinity,
not a cpuset or dedicated-hardware guarantee. CPU model, cgroup, Python,
SQLite, build libraries, filesystem and installed paths are in
`environment.json`. Setuptools license-table deprecation and disabled
byte-compilation warnings are retained in raw stderr; the driver emitted two
tarfile pre3.14-filter deprecation warnings, recorded separately.

The limited package checks pass with the documented auxiliary-helper failure
and independent replacement checks. Full repository/CI qualification belongs
to the integration gate. No benchmark, pressure, new profile, long stability
job, deployment, capacity or production approval is claimed.

## Deployment and rollback boundary

This exercise installs only a local synthetic validation venv. It does not
change service authorities or production deployment. Reproduce against a new
venv; retain the tested artifact hashes and original results. An application
rollback still requires a capability-aware binary for any authority that has
activated durable batching, preserving schema and pending-attempt recovery.
Do not infer that packaging permits an older writer or deletion of authority
state. Stop isolated validation processes and preserve failed evidence before
removing temporary synthetic data.

## Artifact hashes

- `uta_reference_exchange-0.5.0a1-py3-none-any.whl`: 273695 bytes; SHA256 `07defde0d6eb94ca9d64d2bb5d9cec8b45d4d02ba8ccf2ca693aac0ce28cbd59`.
- `uta_reference_exchange-0.5.0a1.tar.gz`: 24806313 bytes; SHA256 `23cf55c3ac41224611151852676fdcaa3e338cbc3dc8ac4ccf640d70b5f0b09a`.
