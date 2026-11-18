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

## Final adaptive closure

The final author commit is **`923b37845bcb588d8e953d49be978034f28a0de8`**. [The independent adaptive checker](evidence/managed-909acec-v4-independent/final/check_adaptive.py) and [its 73-check result](evidence/managed-909acec-v4-independent/final/result.json) verify only JSON/hash/AST and in-memory receipt/clock functions. No product function was imported or called; preflight keys and start flags came from parsing immutable source. This is contract acceptance for possible **separate** root-authorized admission, not phase execution or an issued GO.

| Final artifact | SHA-256 |
| --- | --- |
| Profile | `9ecd5476c347fbf1d767445f6c73a26fde46b026c7008d9b0f24f36e8801213d` |
| Plan | `e0bff7603d5ff236a261a53533c3afede20c40580ba84161350c708a5860e284` |
| Amendment | `432c7c8dec731c154074bf47babcf1d35300cf1432439c76fd02eead29b1b3d6` |
| Commands | `866afbda1bc3ee4b447b4d47406c7ad090906e371be4a3c15c200f6cea6b7822` |
| Single-phase runner | `49c34950c38056be2fdef534a7d252a579fde20bd1d0f5195ec39df0ae527210` |
| Preflight spec | `154010e82fe48d8a63380de34e0df75557a04a6c3385aff10aa74174076c9c4c` |
| Start spec | `934dc15bcf1ec48f482335b0bf79ef9c6b53a65b48f60d1e9a947d770c1702ab` |
| Root outer launcher | `aab22dc68a389d1b4bc4f83c1a59eee1315191e1f4f522546f043e8c36ac6b44` |

R1 is closed: the actual preflight's financial/live/capacity/production false fields are validated distinctly from the start receipt's real `ro.FLAGS`; neither fabricates missing continuous fields. Both phase shapes pass pure positives, while wrong numeric/boolean exits, incomplete stdout and timeout fail. R2 is closed: `budget()` returns the exact clock it validated and `post_hash_clock()` returns that same object. Pure readings at 74 succeed for deadline 75; 75/76 and rolled-back/root-expired readings reject, with exactly one read. The original 74/76 acceptance counterexample stays historical RED.

R3 is closed by **static inspection** of the separately retained root launcher: metadata reads/writes and wait are covered immediately after Popen, `finally` cleans only the unreaped new runner session, and reaped PIDs are never targeted. Primary and cleanup errors remain distinct; bad/nonverified JSON and stderr fail closed. No actual process cleanup fault was injected. Detached supervisors and unrecorded descendants are expressly outside a blanket cleanup claim. The root's new endpoint follows closed/fsynced/read **and hashed** streams; final attestation serialization still follows its own measured endpoint, as explicitly labeled.

The runner's fixed capture and consumer bytes remain 57e/f31, with immediate capture → guard → unique durable phase GO → same-call guard and Popen. External root approval binds spec/profile/runner hashes and exact argv for **one phase**, with positive, forward wall/BOOTTIME bounds up to 180 seconds. Wait and phase limits are 75 seconds each; every observed clock still has to fit the root approval. A preflight result never authorizes start. Unknown start results can leave a detached supervisor running: record UNKNOWN, preserve raw and identities, reconcile it, and do not repeat start. No own-session cleanup is authority to terminate the old 4471/8784 processes or an inferred detached supervisor.

The final plan retains 21,600 actual active seconds, rate .25, 5,400 rounds, worker/parent faults every 30/300 rounds, observer cadence 61 seconds, all 12 half-hour golden blocks, technical unknown budget 3 and consecutive maximum 1. The six-hour clock cannot be shortened to the old job's deadline. Exact source 909 and the existing full3/CI8/package independent commit references remain bound; their tests were not rerun or inherited from another source. Smoke02's `4052…` narrow acceptance and the timing gap are carried explicitly; full business/risk reexecution remains unclaimed.

The declared new 6+2+1+1 GiB and old 6+.25 GiB sum is exactly **17,448,304,640 bytes**. The output budget remains a periodic threshold and clone budget an input estimate; no quota, reservation, maximum overshoot or fresh current free-space pass is inferred. Every new phase still needs a new immutable snapshot whose original producer/latest effective heartbeats fit 15/30 seconds, dual clocks and remaining TTL fit 15 seconds, protected old identity/source/CLI policy matches, and that combined disk floor is met at dispatch. **This review gives no live resource snapshot and no preflight/start authorization.**

No remaining hard blocker was found in this reviewed contract scope. Root can separately review and issue the exact single long-preflight approval only after fresh conditions pass; start requires its own subsequent approval and receipt review. Source remains frozen and all execution/future achievement flags remain false in the preregistration. Reverting this docs-only review has no migration or runtime effect and cannot stop or restart a job.
