# Explicit measurement MemoryError follow-up

Append-only after source-budget fix `08cdef397a44037cca9235a800fee58949574e8f`.
The new one-case test first failed on that exact production code: a controlled
metadata `MemoryError` produced no `terminate_owned` call. The raw initial red
is preserved, matching the independent peer's `memory_unknown_red.py` and
`memory-unknown-red.json` under its c27 review directory.

The production fix adds only `MemoryError` to the explicit measurement boundary's
existing `(OSError, ValueError)` catch. It now uses the same typed
`observer_output_budget_measurement_unknown` technical NO_GO, original owned
producer drain and log ordering. It does not label financial corruption, change
legacy missing-field behavior, or reinterpret any historical unknown as OOM.
The test injects one exception with mocked children; there is no memory pressure,
SQLite connection, producer, service, dummy or long job. The controlled case
proves action-before-log when later allocations and the signal operation work;
it cannot guarantee recovery if subsequent allocations, signalling, native abort
or the OS itself fails. No unsafe fallback kill is introduced.

The same pure target now has40 cases per runtime. `run_tests.py` shares a10s
budget and writes only new evidence paths. Default AST/byte proof is again
archived here. All prior c27/ade/source-fix/peer raw evidence is unchanged.
Qualification, resource admission and execution authorization remain false.
