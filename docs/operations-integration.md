# Managed operations integration

This integration starts at `8eeab43` and combines the five read-view commits
`cbe6516`, `1ed207a`, `57a22f2`, `66fdab3`, `8da82df`, independent view evidence
`9f49092`, and managed-soak commits `0f8de21`, `bbf1f74`, `81c7e5b`, `d73f4ed`,
`70dc281`, `27df46d`. The obsolete diagnostic experiment `8dee09f` is excluded.
The base storage, writer fencing, sharding, process router and request-signing
files remain byte-identical. Existing sanitized gateway diagnostics are retained.

An actual Python 3.10 probe exposed `parse_qsl('', strict_parsing=True)` rejecting
an absent query. Empty queries now explicitly use view defaults. Real HTTP
regressions cover absent and trailing-`?` queries and retain strict rejection of
nonempty malformed/duplicate/unknown fields.

Targeted integration checks, on Python 3.12.14 and 3.10.22 respectively:

| Scope | Tests | Result |
| --- | ---: | --- |
| Read views, exact money, scoped HTTP, query compatibility | 19 | pass / pass |
| Independent managed read views | 20 | pass / pass |
| SQLite kernel lock ownership, storage, startup lease, durable gateway and diagnostic adapter | 27 | pass / pass |
| Managed TLS/HMAC, real matching, debt repayment, worker/parent kill and checkpoint gap recovery | 5 | pass / pass |

Reproduce from this checkout, setting `PYTHONPATH=tests` for the combined suite:

```sh
python -m unittest discover -s tests -p test_durable_views.py
python -m unittest discover -s tests -p test_managed_views_reference.py
PYTHONPATH=tests python -m unittest test_sqlite_lock_ownership test_storage_locks test_worker_startup_lease test_durable_gateway test_durable_diagnostic_adapter
python -m unittest discover -s tests -p test_managed_soak.py
```

The initial combined invocation used Python stdin as its main module, which
cannot be imported by spawned workers; that invocation failed in the test
harness. The recorded successful command above uses the importable unittest
entry point. Expected expired-worker subprocess traces in the startup negative
case are retained in raw logs; the unittest result is successful.

This is targeted integration evidence, not a full-release qualification report.
No new 6-hour/24-hour job was launched. Historical `d73f4ed` 10/60-second results
remain unsafe historical observations and do not qualify this release. Deploy
only in a separate synthetic environment using existing durable CLI procedures;
rollback stops and drains it before selecting the previous immutable checkout.
Do not downgrade a live managed schema or reuse/reset authoritative test state.

## Long-run qualification follow-up

The follow-up replaces the fixed historical blocker with the exact-release
contract in [managed-soak.md](managed-soak.md). Nine gate tests and the five
real managed TLS/process tests pass on both Python 3.12.14 and 3.10.22. Gate
fixtures are explicitly synthetic records used to exercise rejection/acceptance
logic; they are not full validation evidence. Their positive case verifies
preserved report bytes and false production/duration flags. Negative cases
cover all outcome counters, boolean/missing values, contradictory success,
missing/changed log and sidecars, manifest omissions/digest changes, documentation
and untracked dirt, same bytes at a different commit, runtime mismatch, source
movement during qualification, changed stored evidence, API opt-in and rejection
before run/resume state changes.

No complete release validation report has been generated for this final patch
in this delivery. Freeze the integrated commit and run the real full validator
before requesting a future long engineering test. Report acceptance is not a
production approval and does not claim elapsed-time or throughput acceptance.
