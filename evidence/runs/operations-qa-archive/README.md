# Historical QA raw archive

This archive is organized independently from source
`4608ffeda0651f8dafd2cd151618a71ed99aa62e`. It preserves ten original QA records:
three local runtimes for each of `13e6924`, `24ac06b` and `4608ffe`, plus the
original failing `4608ffe` Python 3.10 push-CI artifact's raw members.

`records/local/{source}/{runtime}` and `records/ci/4608ffe-push-python310`
each retain the original `summary.json`, `unittest.txt` and `worker-result.json`
without changing bytes or field types. Before/after source manifests remain
inside those original summaries. The convenience `source-manifest-*.json`
sidecars are explicitly derived value copies with their original JSON pointers.

`records/index.json` identifies original and archived paths and every raw file
hash/size. It retains failed rows as **NO-GO**. `13e6924` passed its three local
1078-test runs; `24ac06b` failed one of 1092 tests in each runtime; local
`4608ffe` failed one of 1096 on Python 3.10 and passed on 3.12/3.13; its separate
CI 3.10 artifact failed three of 1096. Local 4608's owned-startup assertion and
the CI grouped/readiness assertions are kept distinct. Package success and
later corrections do not requalify the failed raw results.

`records/ci-artifact-digest.json` pins the untouched original ZIP and proves its
three members match the archived CI files. The ZIP binary stays outside Git at
`/workspace/uta-ci-4608-push-310/artifact.zip`; only its digest/member metadata is
added. No signed download URL, auth nonce/key, download-response metadata or
financial/auth database is archived.

`records/integrity-check.json` records byte-exact copying, raw/worker/summary
agreement, before/after source manifests matching the exact Git commits, and
original files remaining unchanged. Its PASS is strictly an archive-integrity
result. `records/privacy-check.json` records the named value-pattern checks.
The archived `4608ffe` disposition stays NO-GO; production approval is false.

`collect_records.py` is the exact executed collector. It reads committed source
bytes with Git archive in memory and performs no tests, app imports, SQL opens,
QA rerun or package build. `collection.*.txt` are its actual stdout/stderr.
`commands.txt` describes repeatable integrity checks using new output paths.
The existing MANIFEST covers these file formats; ZIP support is not added.

See [the history report](../../../docs/operations-qa-history.md) for the complete
source/runtime table and evidence limits.
