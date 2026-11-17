# Fixed c507 pure interest kernel: independent scoped acceptance

Candidate `c507e0b458f24d2434ed2c24df597ba171113d3c` passed its first
independent differential execution:68 checks, zero failed checks or exceptions,
Python3.12.14, CPU3, PID508437,121,475,573ns before result serialization.
The result and provenance are retained unchanged beside this verdict. No
repeat execution or production import was used to generate expected values.

The12 manual rational cases were committed before the candidate was imported.
The oracle independently multiplies `Fraction` principal, annual-rate and time
fractions.32 deterministic interval partitions agree with that exact sum.24
lifecycle checks cover immutable historical replay without current-state rewind,
changed-payload/reference conflict, stale CAS, time gaps/overlaps, principal
checkpoint and boundary changes, invalid rate coverage/currency/scale/version,
rejected-command state preservation, risk-unit overflow, invalid typed principal
and the4096-reference limit with old retries still permitted. The manual
standards' separate20-check selftest is not counted as additional candidate
coverage or new unique examples.

The four actual same-process input hashes match both before/after files and
their recorded Git blobs. The candidate adds only its new module and tests;
existing credit APIs, zero-rate policy, native V2 and account specifications
are unchanged from frozen909. Positive fractional carry is retained even after
principal becomes zero. The risk reserve is only an extra minimum unit for
fractional interest; cumulative booked accrual is not unpaid debt.

Acceptance is limited to this single-threaded pure model. The independently
executed set did not include a positive `end == rate.valid_to` case; the source
uses the agreed inclusive coverage check for the interval's exclusive endpoint,
but that boundary is not upgraded to dynamic evidence here. The result does
not prove authoritative clock/event selection, parameter approvals, restart or
cross-process deduplication, concurrency, durable receipt/carry commits, ledger
conservation or automated scheduling. Existing V2 still prohibits new interest
accrual after activation. Full financial integration remains NOT_ACTIVE.

There is no deployment or data migration in this review. Keep the calculator
experimental; a later financial change must persist interval identity, rate,
principal history, carry, receipt and balanced journal effects atomically under
the actual authority. Rollback removes the experimental calculator's future
registration while preserving its inputs and all first results. Do not infer
permission to erase already booked interest or drop fractional carry.
