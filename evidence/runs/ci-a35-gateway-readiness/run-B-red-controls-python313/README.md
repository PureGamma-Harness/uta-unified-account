# RUN-B: two deterministic contract failures, two controls, one cleanup error

Single authorized CPU3 run at source `f164ed0`: 5 cases in 6.147 seconds,
2 FAIL / 2 PASS / 1 ERROR. The original helper rejects real HTTP overload;
the original single owner observation rejects a real control-timeout unknown.
Those are the two planned contract red results, not a reproduction of the
historical CI scheduling/cause. Actual closed-admission and persistent-unknown
controls passed. The real native-lease negative control is **ERROR**, not PASS.

Its two actual final observations have native generation 1, expired lease,
owner_ready=false and ready/financial_ready=false. The parent worker PID had
changed while the persisted lease and READY frame still named the old owner.
The unchanged supervisor source kills, joins and replaces its own expired
child; this is consistent with the observation. Cleanup then found the old
proc entry absent and refused to signal an unknown/replacement PID. Its
FileNotFoundError is retained. No pidfd terminal poll was captured in this
original run, so a later cleanup correction must not backfill that evidence
or relabel this run as a passing negative control.

The old owner's PID/birth and bound pidfd creation are recorded before the
test signals it. Only that private fixture was targeted. Runtime code and the
original one-second lease were unchanged. The fixture's original cleanup
closed all its current children after the case. Further runs require a new
source/evidence directory and integration-owner coordination.
