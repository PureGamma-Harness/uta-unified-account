# Independent PURE7 caller timing-delta closure

**CALLER CODE_ONLY CLOSED** for CODE
`a14d09058a64a7948bfb4ba8985006d116c75752`, tree
`38f58c252ad6115f69be16a005a45d2b0e6720de`, invocation OWN
`2bcd77270234cd91a5dd890ce3ca1171c22ad4a4`, tree
`1842df45aea5c6d31838c1e4ab75e97e078fa618`. This closes
PURE7-CALLER-LATE-EOF-001 on the new source. The old2043075/cb649 NOT_CLOSED
record remains unchanged. No caller/target import, compile, run, SQL, PID
operation, probe or child agent occurred in this review.

`normal_capture_eof` is captured immediately after the original loop. A
separate `timely_completion` becomes true only after normal actual wait/reap,
with that original EOF true, no prior expiry and the clock strictly before
the original30s deadline. Failure/expiry cannot recover that qualification.
Finally has no assignments to the three qualification variables; it may only
supplement actual EOF/exit/reap facts. The required combined check includes
`timely_completion and not deadline_expired`. Thus late EOF plus a genuine
rc0 no longer qualifies, while rc0 remains accurately recorded. Trailer,
actual-exit and CALLER_END disclose the latch state.

Removing only those assignments/check and added output fields reproduces the
entire old caller AST. No other logic or budget changed. Caller19,502B SHA-256
is `4bb62a4f6ff5070f8ad9cf03d316e04692163ce7691d515049a526112a0f9152`;
new caller-plan SHA-256 is
`abf192409daeb4c0a9f155eb657fb58cc67b502d880b7165c1c148c76a75dc94`.
Both match physical regular files and final Git. The old d812 plan is an exact
separate `pure-caller-plan-cb649be-NOT_RUN.json` copy with zero attempts.

All64 target-retained inputs/1,337,823B, entryc84a, pure-planc7c1, financial
sources and both original test files are unchanged. Caller is independently
pinned and not target-retained. The generic CLI permits the proposed new
canonical direct-child namespaces; no old cb649 label is hardcoded into the
path gate. Both new proposed roots are absent at review time.

The reviewed exact invocation scope is the pinned Python with `-I -S -B`,
caller script, `--execute`, actual source HEAD2bcd772, pure-planc7c1,
caller-planabf192, target `/workspace/uta-admission-pure-2bcd772-once01` and
caller `/workspace/uta-admission-pure-2bcd772-once01-host-once01`. It selects
only the seven existing pure methods. This CODE closure does not itself grant
the separate root execution GO.

Existing limits remain target10s/entry completion12s, caller capture/wait30s,
failure reap2s and final drain.2s, target raw32KiB, launcher1KiB including512B
trailer, successful aggregate raw32KiB and logical8MiB. The cleanup allowance
does not extend successful capture. Own held-pidfd lifecycle, protected birth
guard, full terminal/source checks and external observation of the caller's
actual exit/end remain as previously reviewed. No fsync preemption, descendant
reap or filesystem quota is newly claimed. First FAIL/UNKNOWN must remain
original with no retry. Four SQL tests, migration, performance and production
remain unauthorized; only this new safe review pair was written.
