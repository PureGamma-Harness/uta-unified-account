# Owned startup write-gate evidence archive

This commit archives existing evidence only. It runs no tests and changes no
runtime. All seven source files were copied byte for byte from their original
`/tmp` locations; [copies.json](copies.json) records each original path, archive
name, byte count and SHA-256. The original [manifest.json](manifest.json) is
unchanged, including its original absolute paths and dirty-worktree record.

## Exact source and test scope

The final runs recorded runtime commit
`4cce70834fb3daa7d561652ff08a1337e03ce3fd`, on the isolated `4608ffe` baseline.
All 49 `runtime_sources` hashes in the original manifest were checked against
that immutable Git commit when copying. There was no dirty runtime source.

The recorded worktree was dirty in exactly these two files:

```text
 M docs/startup-write-contention.md
 M tests/test_startup_write_contention.py
```

The final contention test bytes therefore must not be represented as a clean
test checkout of `4cce708`. They were subsequently committed in
`8f6fd1e5c6e9c58d0046846db078841cf27ae73c`. All six `selected_tests` hashes in
the original manifest match their files in that final test commit; that equality
was verified by reading Git objects, without executing tests. The dirty prose
document was not a selected test or runtime input. These distinctions are kept
in the original manifest rather than rewriting its commit field to a later SHA.

The archived driver SHA matches `script_sha256`, and all three final log SHAs
match their original manifest entries. The archive hash checks establish byte
identity; they are not signatures or a new test execution.

## Original results

| Log | Python | SQLite | Affinity | Targeted result |
| --- | --- | --- | --- | --- |
| [python310-targeted.txt](python310-targeted.txt) | 3.10.22 | 3.53.1 | CPU 0 | 67 passed, 10.892 s |
| [python312-targeted.txt](python312-targeted.txt) | 3.12.14 | 3.53.1 | CPU 0 | 67 passed, 11.125 s |
| [python313-targeted.txt](python313-targeted.txt) | 3.13.5 | 3.46.1 | CPU 0 | 67 passed, 12.321 s |

The table uses unittest's elapsed times. Manifest `elapsed_ns` includes driver
overhead and the environment query and is intentionally not the same metric.
Each final log reports `OK` without skips. Runs were sequential and used small
synthetic authorities, not large histories or a load generator.

The archived [red log](uta-startup-binding-4608-red-py310.txt) retains the
unmodified-runtime result: two cases, one failure. A real owned writer lock
caused the genuine keeper renewal to raise `OperationalError: database is locked`.
Phase flags and the original cause distinguish that failure from ledger-object
substitution. It demonstrates a reachable self-contention mechanism; it cannot
recover the missing cause of the historical 1096-test full-run failure.

The separate [scoped assertion log](uta-startup-binding-scoped-py310.txt) records
the exact ledger-binding case after its setup and rejection assertion were
separated. The final 67-case selection additionally retains producer BUSY
poisoning, actual-expiry rollback, unknown-COMMIT rejection, complete RO replay,
independent owned-startup reference, storage and writer-fence checks.

## Reproduction and qualification boundary

[uta-startup-binding-final.py](uta-startup-binding-final.py) is the actual driver,
copied unchanged. It retains the original interpreter paths, selects one allowed
CPU and records source/test hashes and combined stdout/stderr. To repeat it on
this host with the matching source and test bytes, provide a new output path:

```bash
python evidence/runs/startup-write-gate/uta-startup-binding-final.py /path/to/matching-worktree /tmp/new-startup-write-gate-output
```

Interpreter paths are environment-specific. A rerun on another checkout or host
is new evidence, not a reinterpretation of these original results. Do not run
against an existing output archive if the original evidence must be preserved.

These are targeted component/regression results for the recorded source and
test bytes. They do not qualify a later root/cherry-picked release, the complete
repository suite, remote CI, capacity, 250k-history recovery, HA or real-money
production. Those gates require their own frozen-source evidence. This archival
operation neither changes nor reruns the original long-running authority.
