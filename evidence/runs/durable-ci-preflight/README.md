# Remote CI failure, preserved before any repair

GitHub run [43971879359](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/43971879359)
tested exact `e6e3afd5b1f07e200a9d7855efb93eb9267bac83`.
All four Python 3.10–3.13 jobs ran 845 tests and failed; the original decoded job
logs and API job metadata are retained here. No deployment/build step passed.

Observed failures differ by job: waiting for a worker receipt returned `None`
after its unchanged finite timeout (3.11 liquidation, 3.12 process recovery,
3.13 independent account capacity); 3.10 reported `fence_guard_corrupt` for table
inventory during a read while managed startup can legitimately add tables. The
3.13 short soak overload fixture also reported only one arrival instead of three.
SQLite version, common cause and correctness impact remain under investigation.
These observations do not prove a SQLite library bug or justify weakening guards.

The earlier local 793-test baseline passed on its own frozen source and library;
it does not override these later remote failures. Follow-up tests add failure-only
diagnostics and display the actual soak error report, preserving monetary
assertions, finite waits, all old-binary rejection and no-repair requirements.
Real production and the candidate integration gate remain blocked until repaired
and independently reverified. The separately running 24-hour source is untouched.
