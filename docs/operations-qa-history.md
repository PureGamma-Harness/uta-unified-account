# Historical operations QA: exact records and failed gates

This archive preserves nine completed local full-QA runs for three distinct
source commits and the original failing Python 3.10 push-CI artifact for
`4608ffe`. No test, benchmark, financial process or package build is rerun by
this collection. Raw results retain their original bytes, field types and
PASS/failure values. A package acceptance result is never substituted for QA.

| Source | Origin / runtime | SQLite | Tests | Failures / errors / skips | Recorded QA |
| --- | --- | --- | ---: | --- | --- |
| `13e6924` | local Python 3.10.22 | 3.53.1 | 1078 | 0 / 0 / 0 | PASS |
| `13e6924` | local Python 3.12.14 | 3.53.1 | 1078 | 0 / 0 / 0 | PASS |
| `13e6924` | local Python 3.13.5 | 3.46.1 | 1078 | 0 / 0 / 0 | PASS |
| `24ac06b` | local Python 3.10.22 | 3.53.1 | 1092 | 1 / 0 / 0 | **NO-GO** |
| `24ac06b` | local Python 3.12.14 | 3.53.1 | 1092 | 1 / 0 / 0 | **NO-GO** |
| `24ac06b` | local Python 3.13.5 | 3.46.1 | 1092 | 1 / 0 / 0 | **NO-GO** |
| `4608ffe` | local Python 3.10.22 | 3.53.1 | 1096 | 1 / 0 / 0 | **NO-GO** |
| `4608ffe` | local Python 3.12.14 | 3.53.1 | 1096 | 0 / 0 / 0 | PASS |
| `4608ffe` | local Python 3.13.5 | 3.46.1 | 1096 | 0 / 0 / 0 | PASS |
| `4608ffe` | push CI Python 3.10.22 | 3.46.1 | 1096 | 3 / 0 / 0 | **NO-GO** |

The exact commits are:

- `13e6924377f031bb3da7ec94aa88df25ed7612ec`;
- `24ac06bc7b9662e1bd215a85ce1b5231e03e37e6`;
- `4608ffeda0651f8dafd2cd151618a71ed99aa62e`.

The historical `13e6924` matrix passed at its own source. It does not establish
QA for later runtime changes. The `24ac06b` matrix and the combined archived
`4608ffe` observations remain **NO-GO**. Later focused fixes or a new package
PASS do not turn these original failures into passes; a later source requires
its own recorded qualification. Production approval is false throughout.

## Preserve the different failures

All three `24ac06b` runs fail
`test_worker_quarantine_is_not_risk_rejection_or_acceptance`; the raw assertion
compares the complete stored-table snapshot after a failure diagnostic event.
The archived failure is not reclassified or removed here.

The **local** `4608ffe` Python 3.10 failure is
`test_real_verified_context_cannot_be_rebound_to_a_different_ledger_object`.
The recorded assertion observes `startup_keeper_failed` where the test requires
`startup_not_verified`. That is separate from the **CI** failures:

- `test_real_submit_cancel_and_response_loss_retry_preserve_one_business_effect`
  receives `503 command_result_unknown` instead of its required 201;
- `test_real_activation_precedes_parent_ready_pipe_consumption` fails on
  `shard_unavailable`;
- `test_successful_activation_does_not_force_a_contended_observation_true` also
  fails on `shard_unavailable`.

The original CI readiness reports lack the underlying SQL exception/code.
Separate lock-contention reproductions can establish a classification gap, but
cannot identify locks as the unique cause of these CI observations. This archive
does not merge local and CI failures into one cause or claim that financial
unknown outcomes were accepted.

## Raw bytes, source identity and CI ZIP

The [archive index](../evidence/runs/operations-qa-archive/records/index.json)
records every original path, archived path, byte count and SHA-256. Original local
records are under `/workspace/uta-operations-validation/{source}/{runtime}/`.
The CI originals are under `/workspace/uta-ci-4608-push-310`. All thirty original
`summary.json`, `unittest.txt` and `worker-result.json` files are copied without
rewriting. Each summary's log digest matches the archived raw log; its worker
result and test/failure totals agree with the raw runner footer.

The original before/after source manifests are fields inside each raw summary.
Their 203 / 205 / 206 selected-file hashes are independently compared with the
corresponding exact Git tree, and the before/after mappings agree. The collector's
scope is Python files in its six source/test/tool folders, every fixture file,
and `pyproject.toml`, `MANIFEST.in`, `LICENSE`; it is not the package verifier's
all-tracked-file inventory. Standalone before/after JSON files are explicitly
marked **derived value copies**, retaining the original JSON pointer. They do
not replace or edit the original summary.

The CI `artifact.zip` remains untouched at its original path. SHA-256 is
`bd20e985bd53e58572b3a2f5dba0860799ba55750ce9c2e02c9fd20b271c366d`;
size is 42199 bytes. Its three members exactly match the three archived CI raw
files. The ZIP binary is not duplicated in Git, so no ZIP manifest rule is
added. Its digest and member hashes are retained in
[`ci-artifact-digest.json`](../evidence/runs/operations-qa-archive/records/ci-artifact-digest.json).

No download metadata or signed URL is copied. Named nonce/secret/key-value,
Bearer-value, private-key-block and query-URL pattern checks find no matches in
the raw files; test names and source filenames containing those words are not
credential values. Input files are rehashed after collection and remain
unchanged. The [integrity result](../evidence/runs/operations-qa-archive/records/integrity-check.json)
qualifies the archive copying only, not QA or production. Existing manifest
rules cover every new JSON/text/Markdown/Python record; the static inclusion
check builds no new package. No authority or auth database is opened.

Reproduction/verification steps are in the
[archive commands](../evidence/runs/operations-qa-archive/commands.txt). These are
historical records, not a six-hour, sustained-capacity, HA, custody or real-funds
qualification. `production_approved` remains false.
