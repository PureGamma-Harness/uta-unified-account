# SQLite diagnostic fixture compatibility

The observer diagnostic already treats native SQLite exception attributes as
optional. The test instead read `sqlite3.SQLITE_ERROR` unconditionally, which
is absent in the hosted Python3.10 interpreter. That raised an AttributeError
inside the assertion after the real missing-table exception was handled.

This change touches only `tests/test_observer_read_diagnostic.py` and review
evidence/docs. The missing-table fixture now inspects the real exception:
when native metadata exists it independently requires integer1 and the name
`SQLITE_ERROR`; when absent it requires null metadata. It never relies on a
module constant export or manufactures fields on an exception. Message
redaction, message digest, error type and output-field checks remain strict.

Two additional fixtures cover a genuine Python-created SQLite exception
without native fields and a module proxy which hides only `SQLITE_*` exports.
The proxy delegates connect/Error to the real interpreter, so the error still
comes from a fresh in-memory engine. It proves the assertion does not require
constant exports while preserving the actual metadata contract.

## Original failures and short verification

The immutable base is `bb34b5fb4397f485c04fe440557b24bb28d1cae2`.
The first evidence-only commit `9ea6ab0` preserves original failed ZIP bytes
and all three members from push44082854090/job134037603227 and
PR44082861767/job134037629772. Both ran1411 tests with0 failures,1 error and
0 skips. Their252 before/after source input hashes equal exact bb34. The
PR's original merge identifier `ff279680ef869954c1ddbfad81a82562190d9c06`
is retained; it is not rewritten to the branch head. Original remote red
results and the separately reported local full-suite red remain historical
NO_GO. This repair does not reclassify either as passed.

The tests-first snapshot and actual initial red logs are retained. Python3.10
produced2 errors with both its original assertion and the no-export proxy;
Python3.12/3.13 each produced1 error in the proxy. After the test-only fix,
all three actual interpreters passed9 tests each, no failures/errors/skips.
The3.10 real native exception had no attributes and produced null;3.12/3.13
had actual native integer1/`SQLITE_ERROR`. Python-created exceptions had no
native fields on all three runtimes. Both rounds used CPU2 and together took
less than one second of recorded child wall time. No full suite, service,
benchmark, live job SQL or persistent financial database was started.

Every original runtime/source asset under uta/tools/benchmarks/formal/scripts/
config/deploy plus packaging configuration is byte-identical to bb34; the
complete comparison map is included. No diagnostic runtime, rule, ledger,
account, API, migration or financial behavior changed.

## Reproduction and delivery gates

Evidence is under `evidence/reviews/observer-py310-fixture/`, including original
ZIPs, original source maps, independent read-only archive verification,
tests-first source, red/green actual logs and source before/after hashes.
To run only this small fixture group in a selected interpreter:

```sh
python -B -W error::ResourceWarning -m unittest discover -s tests -p test_observer_read_diagnostic.py -v
```

The recorded multi-runtime driver is `short-tests/run_short.py`; it requires
a new stage name so it never overwrites an original run. These short greens
are not replacement full QA, CI, package, smoke or six-hour evidence. The
integration owner must create a new immutable source and rerun all required
full3/CI8/package gates before further qualification.

Rollback reverts this test-only patch in a new commit and retains the original
failure archive. It makes no runtime or data change; no database migration or
financial rollback applies. Real-funds and production approval remain blocked.
