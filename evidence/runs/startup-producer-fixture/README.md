# Producer BUSY fixture: preserved CI and controlled setup expiry

The original PR result is retained byte for byte in `original-ci/`: artifact
14310790845, SHA-256
`097dd0d4e266d82a85404c32c9e9c6ec8ea19c7bd8817831b76a6c4b44893bdf`.
Its merge commit is `bd8e5b452166477bb15adeb5807f2c1b98b782ab`. All 208 source
hashes in its unchanged summary match
`7ae94eb8a783f8e134ac90c11a713df7bb02d5f1`. [copies.json](copies.json) records
each original path, copied name, byte count and SHA. No original file is edited.

The original result is 1110 tests, zero failures, **one error**, zero skips,
CPython 3.12.16 / SQLite 3.46.1. The error is in
`test_uncoordinated_producer_writer_busy_is_still_technical_poison` during
`self.fixture.construct(initialization)`: keeper renewal raises `lease_expired`.
The test has not reached the injected producer writer. It must not be called an
expected BUSY result, a passing test or proof that the producer assertion ran.
The stack establishes the actual expiry, not the unique environmental cause of
that expiry. Other runs passing the same bytes do not overwrite this result.

`controlled-pause-old/` adds one deterministic reproduction on the unchanged
7ae runtime and original test bytes. The actual driver
[uta-producer-fixture-pause.py](uta-producer-fixture-pause.py) wraps construction
with a real 0.55-second SIGSTOP/SIGCONT pause of its own process. Its helper
resumes only its still-live parent. It never pauses another service, mocks a
clock, manufactures a token or replaces SQL errors. The old fixture acquires a
real .4-second lease; the controlled run records an actual 550,330,631 ns pause,
`lease_expired`, construction entered but not returned, and no producer entry.
It reports one error. This proves the short fixture's setup assumption is
vulnerable to a real pause; it does not assert that SIGSTOP caused the PR error.

The approved test-only correction will give **only this external producer BUSY
negative** the actual production-default five-second lease from first acquire
through context construction and renewal. Other .4-second self-writer, real
expiry and cross-TTL tests remain .4 seconds. Runtime, TTL policy and SQLite busy
timeout implementation remain byte-identical to 7ae. The negative test will
observe the actual keeper loop within a finite 2.5-second budget, hold the real
producer writer at least .2 seconds (longer than the unchanged default .1-second
busy timeout), and wait for the original `_fail` observation before releasing
the writer. It will retain exact original SQLite `OperationalError`/locked
assertions. Setup expiry, a different error or an unreached producer stage must
still fail; none may be accepted as a successful negative test.

This first commit preserves the red result and correction plan. It contains no
runtime or fixture change, no CI rerun, and no whole-repository, capacity, HA or
production qualification. Follow-up evidence must distinguish the changed test
bytes from the unchanged runtime and retain this original failure.
