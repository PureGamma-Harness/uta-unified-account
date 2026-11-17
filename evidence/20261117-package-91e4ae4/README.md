# Fresh exact-source package evidence: 91e4ae4

**Package scope PASS; full qualification separately pending.** This subsequent
report commit is outside the frozen 3,633-file source. Source:
`91e4ae40b5e9b884c54026406299df5000c9c100` at `/workspace/uta-observer-freeze-91e4ae4`.
New work is `/tmp/uta-release-91e4ae4-k1knnpel`; binaries, synthetic DB/auth/TLS
fixtures and negative archives remain external. No prior binary/installation
was reused. No original job/source/clock/PID/affinity was changed.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 279432 | `eb0ea541abd984697e23ee36d0ca437bf6177d50078010b763f54ede827b2de5` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 34062422 | `aa42b4b40adafd58c82a8df8ab66f262f6b5591d4bc4a06218fb4d4ed344d865` |

All 3,633 tracked files match source/Git archive/sdist exactly. Dynamic runtime
52 files match both artifacts and new installed modules; source-proof.json
contains every tracked hash. Runtime comparison recomputes original d421 Git
blobs and confirms equal bytes, without borrowing execution results.

| Fresh check | Actual count | Result |
| --- | ---: | --- |
| Primary positive gate | complete seven checks | all true |
| Isolated installed CLI/protocol | 8 | PASS, no skips |
| Console commands | 8 | exit 0 each |
| Installed read views | 3 | PASS, no skips |
| No-Git legacy / archived profile / release verifier | 7 / 1 / 19 | PASS |
| No-Git repaired historical reference contract | 10 | PASS, pure |
| Actual runtime omissions | 2 | expected primary exit 1 |
| Actual single historical ZIP omissions | 11 | expected primary exit 1 |
| Report-only physical/member/full-matrix inspection | 13 | PASS |

| Primary check | Positive | Wheel runtime omission | Sdist runtime omission | Each single-ZIP omission |
| --- | --- | --- | --- | --- |
| version | true | true | true | true |
| wheel_runtime_exact | true | false | true | true |
| sdist_runtime_exact | true | true | false | true |
| sdist_required_files_exact | true | true | false | false |
| legacy_fixture_pinned | true | true | true | true |
| legacy_fixture_licensed | true | true | true | true |
| entry_points | true | true | true | true |

Runtime omission target is `uta/failure_diagnostics.py`. Every negative has
exactly the seven check keys and expected false set, physical SHA and size,
unchanged other positive artifact, same source/runtime/version/helper map,
exact missing set and no mismatched source. Independent report inspection
requires only one removed target, no added/changed member, exact remaining
bytes/stable metadata/order and unchanged wheel comment/RECORD. Shifted
physical offsets are excluded. The frozen collectors are unmodified.

All eleven sorted ZIP targets have explicit original reference-commit,
reported code-commit and byte-hash provenance. Each original ZIP matches the
positive sdist and unpacked tree, its three original raw files/log hashes,
worker counters and original Git input hashes. The prior ten registrations
are unchanged. The added `capacity-history-8b/ci-original-pr312` ZIP uses source
8b7f544, reported merge5cdc9b5, original1472tests/1FAIL/0ERROR; that historical
NO_GO is retained. These outcomes are never current candidate CI success.

Actual core commands, cwd, exits, UTC/monotonic durations and environment are
in raw/execution.json and raw/commands.txt. Fresh `git archive` build source
and unpacked sdist have no `.git`; PYTHONPATH is cleared and no dependencies
are downloaded. CPU2 affinity is shared host, not a cpuset/exclusive host.
Max core command 20.471s; archive collector
132.412s; thirteen-case read-only inspection 14.450s.
The new historical-source contract takes0.270s and opens no DB/runtime/service.
Original extraction deprecation warnings remain in raw stderr; there was no
failed/retried package phase or checker attempt in this new run.

The explicit public allowlist screens private material and copies only safe
text/JSON/Python originals, including 118 bound original files. No release or
negative binaries, new CI ZIP binaries, auth/TLS files, financial DBs or signed
URLs are published. `public-allowlist.json` binds exact original bytes and
paths; `evidence-manifest.json` binds published outputs. Original external
archives and all raw results are retained; no old venv/build/job was deleted.

Free space after actual archives: 18,873,823,232 bytes; timestamped proposed
16.25GiB arithmetic margin 1,425,518,592 bytes. This is
not a reservation, physical hard quota, cohost-floor approval or long-run GO.
Integration must remeasure after all QA/package changes and before new preflight.

To inspect without rerunning package execution, use published
verify_control_bindings.py with `--source /workspace/uta-observer-freeze-91e4ae4`,
`--work /tmp/uta-release-91e4ae4-k1knnpel`,
`--records /workspace/uta-package-91e4ae4`,
`--provenance /workspace/uta-package-91e4ae4/ci-zip-provenance.json`
and a fresh `--output` path under CPU2. Original external artifacts are needed.
A complete rerun requires entirely new report/work paths; drivers reject
existing evidence outputs. See [deployment/rollback](../../docs/release-package-91e4ae4.md#deployment-and-rollback).

No pressure, variant benchmark, 60-second smoke or six-hour job was executed.
Full local/CI, capacity, HA, Native V2, complete product coverage, production
and real funds are not qualified by this exercise.
