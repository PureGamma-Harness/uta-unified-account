# a35 exact-source QA archive: NO_GO

Frozen source: `a35fd56fc98126b3e5cced8a459bd04ca580e537`. The three local full runs
passed, but push and PR CI each contain a failing unit job. **The release and
performance GO gate remains NO_GO.** Six successful package validations do not
override those failures. This archive runs no test, SQL, service, profile or load.

## Local full results

| Recorded runtime | SQLite | Tests | Failures / errors | Result | Actual test seconds |
| --- | --- | ---: | --- | --- | ---: |
| python312 / 3.12.14 | 3.53.1 | 1243 | 0 / 0 | PASS | 258.957890 |
| python310 / 3.10.22 | 3.53.1 | 1243 | 0 / 0 | PASS | 256.416925 |
| python313-sqlite346 / 3.13.5 | 3.46.1 | 1243 | 0 / 0 | PASS | 267.100380 |

All local reports preserve their original UTC, exact interpreter, raw command,
source manifests and complete logs. `local/matrix-summary.json` records the
actual sequential CPU-1 cohosted run (10:36:57–10:50:00 UTC), and the external
launcher is retained with its actual `8b40d75b...` SHA. It is an external QA
launcher, not part of the frozen production runtime. All 227 validator input
hashes match exact frozen Git bytes before and after each run. There are zero
unit skips, expected failures, unexpected successes or observed ResourceWarning
lines in these reports; CI step skips are recorded separately below.

## Original CI results

| Event / run | Python | Tests | Failures / errors | Unit gate | Package gate |
| --- | --- | ---: | --- | --- | --- |
| push / 44066483487 | 3.10 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |
| push / 44066483487 | 3.11 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |
| push / 44066483487 | 3.12 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |
| push / 44066483487 | 3.13 | 1243 | 2 / 0 | NO_GO | SKIPPED after failed unit job |
| PR / 44066492849 | 3.10 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |
| PR / 44066492849 | 3.11 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |
| PR / 44066492849 | 3.12 | 1243 | 0 / 1 | NO_GO | SKIPPED after failed unit job |
| PR / 44066492849 | 3.13 | 1243 | 0 / 0 | PASS | PASS: 8 installed cases + 8 commands |

Push Python 3.13 has two actual failures:

- `test_full_original_id_flow_accepts_an_actual_running_unknown_reply`
- `test_delivered_ready_frames_cannot_override_future_or_stale_market`

PR Python 3.12 has one actual error:

- `test_old_inflight_writer_is_drained_before_complete_ro_replay`

The complete original unit logs, both original failed ZIP bytes and two decoded
job logs are preserved. `artifact-catalog.json` includes all eight actual job
step conclusions. On the two failed jobs, later compile/model/build/install
steps were skipped; those missing package artifacts are expected skips, not
download gaps. This evidence alone does not establish a unique failure cause.
No rerun, suppressed failure, changed timeout or fixture repair was performed
by the archivist. Investigation and any later result need separate commits.

## Source and artifact identity

All eight original CI unit reports have 227 before/after input hashes, each
matching exact a35 Git blobs. Push reports keep code commit a35. PR reports
keep their actual merge commit
`2959d4dec3941d8898f60d27fee8bd15fbd452e8`; they are not rewritten to the head.
An independent GitHub Git-commit read confirms the merge tree and a35 tree
are exactly equal: `bb572e91eb0d018cc265b4e229bc2a0944bd16d9`.
`source-identity.json` records the original parents and both identities.

All fourteen validation artifact ZIPs match their catalog SHA and byte count.
ZIP member names, duplicates, relative paths and symlink types were checked
before extraction; every decompressed byte and member digest is preserved.
The two failed unit ZIPs are also committed verbatim. The twelve other ZIP
originals remain outside the repository under `/workspace/uta-ci-a35-all`;
all original members are included here. No wheel/sdist binary is copied into
this archive. Their actual per-CI hashes remain in each package report.

For all six successful package artifacts, the manifest reports exact inclusion
of all 1,961 tracked source paths, no missing/mismatched files and all archive
checks passed. Their 51 runtime hashes and canonical runtime-tree digest were
independently compared to a35 Git bytes. The fresh isolated installed reports
show 8/8 tests, zero skip/error/failure, eight successful console commands,
exact version 0.5.0a1 and the frozen CLI-helper hash. All recorded imported
modules are under the installed site directory. This archive checks preserved
evidence; it does not execute another installation or claim the original CI
environments are still available.

Each successful package ZIP contains exactly the configured 19 report members:
archive manifest, installed report, unit log and sixteen console stdout/stderr
files. The exact allowlist excludes authority directories, SQLite/WAL/SHM,
authentication databases, signing profiles and TLS key files. The selected
raw evidence was also checked for signed-download query patterns and private
key payload markers before publication. No URI credential is archived.

## Retrieval history and reproduction

The integration owner originally reported six missing downloads after a
short-lived file-reference HTTP 403. Two failed unit ZIPs were already held
elsewhere and were reused only after SHA comparison; no tests were rerun.
Fresh direct `gh api` ZIP retrieval of the other four returned no bytes, with
nonzero status and sanitized error digest retained. A fresh GitHub download
plugin reference followed immediately by byte retrieval then recovered all
four, each with the exact catalog SHA. These are transport observations and
do not change any CI business/test result. `retrieval/` keeps safe receipts
and the direct-download driver; signed URLs were never printed or saved.

The [archive driver](archive.py) copies original members, recomputes their
hashes and derives [the index](index.json). It only reads the recorded external
files, Git blobs and original merge metadata; it does not invoke a test runner,
SQLite or any exchange service. Reproduce in a new independent a35 worktree
with the same external source directories available and a fresh archive output
directory. Existing archive files are never silently overwritten.

## Deployment, rollback and limits

This is a report-only delivery with no account or storage-schema migration.
Publishing or cherry-picking it does not deploy the fixed runtime or approve
real funds. Reverting this evidence commit affects only future report visibility;
keep external originals, failed artifacts and their identities for audit.
It cannot roll back confirmed orders, release in-flight funds, reset long-run
coverage or erase an original result.

All release, short-performance GO, 10,000/s, HA/AZ, six/24-hour stability and
real-funds approval conclusions remain unapproved. Local/full, CI/unit and
CI/package results are separate scopes. The continuing long jobs were not
read, restarted, signalled or otherwise changed by this archive task.
