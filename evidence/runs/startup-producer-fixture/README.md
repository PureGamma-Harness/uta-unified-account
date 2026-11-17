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

## Test-only correction and controlled green

The correction adds a fixture parameter whose default remains .4 seconds. Only
the external producer BUSY test sets that instance parameter to 5.0 **before**
fixture setup, so both its very first `acquire` and its context use five seconds.
The case asserts the original acquisition event has exactly a five-second TTL.
All other tests retain the original .4-second parameter, including self-writer
and actual-expiry coverage. No test claims .4-second setup availability here.

Construction and lifecycle checks still sit outside the expected rejection
assertion. Once healthy, the real producer transaction holds its writer while
the actual keeper loop is observed within 2.5 seconds (its ordinary cycle is
5/3 seconds). It retains the lock at least .2 seconds and until a call-through
observer has recorded the **original** `_fail` error. It does not fabricate the
error or modify failure flags. The exact rejection must retain the original
SQLite `OperationalError` containing `locked`; any setup failure, different
cause or unreached keeper attempt still fails. Observed renewal arguments must
remain TTL 5.0 and SQLite busy timeout .1, confirming the production-default
timeout behavior has not been changed.

`controlled-pause-new/` uses the same archived driver and the same real pause
with the corrected test bytes. It records a 553,992,498 ns pause, first-acquire
TTL 5.0, construction entered **and returned**, producer entry, and the genuine
`OperationalError: database is locked` with code 5 / `SQLITE_BUSY`. The negative
case passes in 1.920 seconds. This is not an assertion that setup or a five-second
lease tolerates arbitrary pauses.

The green result's recorded commit is the preceding evidence-only `5690629`,
while its two recorded test-file hashes identify the then-dirty correction bytes
committed in this correction. It is not a clean-checkout run of `5690629`.
All 49 recorded runtime hashes match the immutable 7ae base; the actual driver
is unchanged between controlled red and green. The original manifests/results
are retained without editing their commit or hash fields. Three-runtime
targeted validation remains a separate follow-up; no full CI was rerun.
