# Tiny functional wiring evidence

No performance experiment was executed. All durations below are test-run
elapsed times, not throughput or latency qualification.

| Runtime | Targeted tests | unittest elapsed | Result |
|---|---:|---:|---|
| Python 3.10.22 / SQLite 3.53.1 | 6 | 5.037s | PASS |
| Python 3.12.14 / SQLite 3.53.1 | 6 | 5.482s | PASS |
| Python 3.13.5 / SQLite 3.46.1 | 6 | 5.524s | PASS |

Each target suite initializes four fresh synthetic authorities and schedules
8 orders per case over 0.05s: default0/0/False, same-capability0/0/True,
batch3/cache8/True, batch8/cache100/True. Settings observed in actual spawned
PIDs and independently reopened immutable capability markers must agree.
All 96 final-suite orders are financially SUCCEEDED with persistent OPEN
reservations, zero matches/fills/positions, zero internal retry, no batch
failure, and successful exact balance/version/audit/ledger reconciliation.
PYTHONWARNINGS=error::ResourceWarning and final forced gc are enabled; no
ResourceWarning was observed. The initial Py3.12 five-test run is retained
separately (32 orders); a direct CLI run proves the actual entrypoint passes
all three options to a real child (8 orders). Total retained financial
orders: 136. Each authority has its own identity/CID namespace.

Eight existing retry-gate tests pass on Py3.12 (0.025s), including the immutable
old S1 failure. They do not execute a new load. No profile is produced.

`execution.json` preserves exact commands, UTC starts/ends, subprocess wall
time, source hashes, and private output paths. `functional-runner.py.txt` is
the exact runner. `functional-cases.json` retains selected and executed counts
without presenting them as successful or physical COMMIT counts.
`cli-execution.json` describes the direct tiny CLI run. Every raw authority
export retains its original manifest; the outer manifest covers these
manifests too. No authority database is committed.

Tests ran on parent e9ec23bf0a54f732b51b91df1bad571dd186dba3 plus the uncommitted
OWN helper patch. Environments truthfully report working_tree_dirty=true;
the exact generator/UTA hashes, final test/preregistration hashes and tool.patch
identify the tested code. UTA runtime is byte-identical to that parent. These
functional checks do not replace final frozen-source full QA/CI/package
qualification or authorize any baseline, profile, capacity or stability run.
