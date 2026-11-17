# V4 independent preparation review

This is a pure file/AST/literal review. No long preflight, long start, capture, job directory, SQL, database, service or process was run by the reviewer. The independent actual smoke02 result is `4052b708b74786a6b8ea8648868f0714817bfa1c`; its narrow acceptance is not reinterpreted as a long-run signoff.

## Retained initial candidate

The initial runner SHA is `960ddbcc09a46052706c732526d923f5bdd5caaaf3287782cd21e11521c632de`. Its exact runner/profile/plan/amendment/commands bytes and hashes are retained under [initial](evidence/managed-909acec-v4-independent/initial/manifest.json). The candidate was never executed. The original pending independent-smoke reference is part of that retained historical candidate, not a claim that the later acceptance did not occur.

[Independent pure AST witnesses](evidence/managed-909acec-v4-independent/initial/pure_counterexamples.py) preserve these findings:

- **R1, real preflight schema:** the immutable product's preflight return contains `financial_6h_passed` and `live_coverage_passed`, but no `continuous_6h_stability_passed` or `continuous_24h_stability_passed`. The initial shared future-flags validator rejects the real successful direct shape. Fix must validate the actual phase-specific fields; adding fabricated continuous fields to the receipt would conceal the mismatch.
- **R2, returned endpoint unchecked:** `post_hash_clock()` calls `budget()` using one clock, then returns a second clock without validating it. The pure witness has the first reading 74, phase deadline 75, returned reading 76. It returns an expired endpoint. Validate and return the same reading, including both root clock bounds, the phase deadline, and pipe-failure state.
- **R3, root launcher fallible window:** the retained root launcher creates its runner process, then reads birth and writes the Popen record before entering the wait/cleanup `try`. A failed metadata read/write in this interval can abandon an already running owned runner. This is a static path finding; no process was created to demonstrate it. Register/cover that owned unreaped Popen immediately with bounded cleanup and typed UNKNOWN. Do not infer or signal a detached supervisor, and do not repeat a start after UNKNOWN.

Original [pure counterexample output](evidence/managed-909acec-v4-independent/initial/pure-counterexamples.json) remains unchanged. The old candidate is not approved for execution. Final candidate closure is to be recorded separately with exact final hashes.

The intended policy remains reasonable: each single phase binds external root approval to spec/profile/runner and exact command, uses a fresh 57e capture and f31 guard immediately before Popen, and permits no automatic next phase. A 75-second fresh-window wait and 75-second phase bound may fit a 180-second root approval only when each actual clock remains within that approval; no promise follows merely from adding configured budgets. Long-start acceptance confirms only a supervisor-start receipt pending the actual driver, not a running six-hour result. Unknown detached-start results require identity/status investigation before any further action, with no automatic retry.
