# Explicit source-budget binding follow-up

Append-only fix after `c27ced8306009106f9da720179fa53b1080f2c91`; the original
policy/evidence and independent red are not rewritten. Peer source counterexample
`source_budget_red.py`/`source-budget-red.json` lives under
`/workspace/uta-managed-output-budget-peer/evidence/reviews/managed-output-budget-c27`.
It demonstrated that a correctly rehashed explicit2GiB output plan declaring
source1GiB was accepted although the unchanged producer Configuration default
is6GiB and the command has no source-budget override. The understated admission
amount was5,368,709,120 bytes. This was pure JSON/AST, not an executed producer.

The shared resolver now requires an exact int6GiB source declaration only when
the new output field is present. That resolver already serves real read_plan,
preflight, supervise, prepare profile/prepare/invoke entrypoints. Tests exercise
the actual hashed JSON paths and verify rejection before Popen, subprocess,
mkdir or operational imports. Missing, bool, float,1GiB and7GiB values are
rejected; the counters and raw preregistration bytes are unchanged. Correct6GiB
is accepted. Missing-output-field plans retain historical behavior, including
their old source declaration handling; this is not retrospective requalification.

Production command/default, sampling, financial and coverage rules are unchanged.
The prior correct6+2+1+1+6+.25GiB arithmetic is unchanged. The original14:05
metadata observation is historical resource diagnosis and remains NO_GO, not
qualification or current reservation. No new cohost observation was made.

`run_tests.py` uses the original pure target list, with a shared10-second outer
test budget and new output paths so no previous test log is overwritten. It
selects no PIPE/dummy test, and uses no SQL, producer, service or long job.
The new source-budget class adds three tests to the prior36-case target.
Default-compatibility AST/byte proof is re-executed to a new JSON path here;
all original producer/observer/coverage/UTA and preregistration bytes still match.
