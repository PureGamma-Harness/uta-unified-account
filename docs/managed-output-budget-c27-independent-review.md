# Independent review: explicit output budgets

Original reviewed commit is
`c27ced8306009106f9da720179fa53b1080f2c91`, based on8b. **Original c27 has
two reproduced policy blockers.** Both are addressed in author commits
`08cdef397a44037cca9235a800fee58949574e8f` and
`499fd357ada91a7eefbb78d00a4763a4c2cc60d9`; independent pure controls against
exact499 module bytes close these two findings. No remaining blocker was
found for this scoped integration. This is not approval to start a smoke,
long run, production or real-funds service.

## Preserved red findings and closure

| Finding | Original actual pure result | Fixed result |
|---|---|---|
| BUD-R1: producer declaration is not bound to actual cap | A newly hashed explicit2GiB output plan declaring source1GiB is accepted by real read_plan. The actual producer Configuration AST defaults to6GiB, the CLI constructor does not supply max_directory_bytes, and the actual producer command has no override. Reservation is understated by5,368,709,120 bytes. No process is started. |08cdef checks the shared explicit-policy resolver for exact integer6GiB, including missing/bool/float/wrong values. The same read_plan counterexample now raises the typed policy error before external effects. Legacy missing-field behavior is unchanged. |
| BUD-R2: allocation failure while measuring is not a resource drain | A controlled MemoryError in the metadata measurement call reaches the actual outer supervisor collector handler, records supervision_collection_error, and requests zero producer drains. All children are mocks; no physical OOM or pressure is exercised. |499fd adds MemoryError to the explicit measurement boundary. Independent call-through with the same injected unknown records one owned drain before the typed technical log and keeps financial_corruption_inferred false. |

Original scripts and result JSON remain under
`evidence/reviews/managed-output-budget-c27/`. Each deliberately exits1 on the
original accepted defect; the red metadata is not revised to green. The fixed
candidate control is separate. Initial red logic used real plan/AST parsing and
a real supervisor function with mocked child lifecycle, not a replacement
supervisor oracle. Fixed source hashes for all4 loaded files equal exact499
Git blobs and remain unchanged through the control. The three small controls
took0.01595,0.00212 and0.00453 seconds on CPU3, below the5-second bound.
There was no SQL, producer child, service, benchmark, physical OOM or old-job
read. Strings naming old report paths in a copied public plan were never opened.

R1 applies to the new explicit policy. It is not a claim that the existing
registered6GiB plans or the timestamped6+2 arithmetic were already wrong.
The reviewed producer cap remains6GiB; a future producer contract change
requires matching validation and qualification rather than silently relying
on a stale declaration. The repair intentionally does not reinterpret ad hoc
legacy declarations as newly validated resource claims.

## Static integration checks

The missing-field branch returns historical6GiB before applying new explicit
rules. Its original three-file timeline/latest/baseline measurement and
collection-error-only behavior are retained; it is not a complete output-tree
budget and does not newly drain on counted control-file growth. An explicit
value opts into full control/observer metadata measurement, even if equal6GiB.
It must be an exact non-bool integer from1GiB through6GiB. The shared resolver
is used by read_plan/profile/preflight/prepare/invoke/supervise, so the corrected
producer binding and output sum agree before starting this new mode.

The full traversal anchors each opened directory FD with nofollow and verifies
child device/inode after open. It stats regular-file metadata without opening
contents. Symlinks, special files, missing/unreadable metadata and excess depth
raise unknown. The direct private-audit parent and matching
private-full-clone-[a-z0-9_]{8} clone directory must have current UID/mode0700;
only those clone subtrees are excluded. Unknown sibling names are counted.
Excluded descendants are still traversed for invalid types/symlinks. This is
naming/ownership metadata validation, not proof of a physical peak-clone quota.

A strict over-budget or measurement-unknown event invokes this attempt's
original owned driver's official drain before fallible error-log IO. Parent
output-write OSError follows the same ordering. Failure records are technical,
not inferred financial corruption. Popen ownership/birth and protected4471/
8784 checks are unmodified. No old process is adopted. This review did not test
real signal delivery, persistent disk-full handling, operating-system death,
actual clone IO or a real drain completion; a request is not a confirmed stop.

Independent AST checks verify unchanged Pipes, Timeline, producer and observer
commands, original financial drain, request_observer_stop, authorization,
cohost-budget and smoke-drain helpers against8b. Git bytes for UTA, producer,
observer/coverage/smoke logic and all old plans/profiles are unchanged. The new
MemoryError catch is only at the explicit metadata measurement boundary;
other coverage/telemetry error policy and original clock/financial gates stay
separate. Pre-start budget validation is covered by the new-source policy;
this is not blanket validation of every possible malformed legacy plan.

## Resource meaning and remaining gates

The30-second collection-loop eligibility interval can be delayed by synchronous
helpers. It provides no atomic tree snapshot, OS hard quota or guaranteed
overshoot bound. Logical stat sizes and separately admitted clone estimates
are not physical reservation or cache-hit counts. Output may continue during
drain/final audit, so the policy must not be advertised as a hard2GiB disk cap.

With a correctly bound source6GiB, future output2GiB, clone estimate1GiB and
headroom1GiB, new demand is10GiB. Adding old full6GiB plus the separately
reviewed256MiB floor gives17,448,304,640 bytes. The author's14:05 metadata
observation reports20,648,210,432 free bytes, leaving3,199,905,792 arithmetic
bytes. This reviewer read only that committed report, not any live job.
The observation is neither current reservation nor qualification, and the old
observer floor is not a hard cap. Fresh cohost/space checks remain mandatory.

Original8b remains NO_GO. The integrated exact source requires fresh full
local QA, all CI jobs, actual package/negative controls and independent review
before a new profile can receive phase-specific execution approval. No sample,
financial assertion, historic budget or clock was relaxed by this review.
Rollback reverts the new tools/policy in a new commit and retains all red
records; it must not edit an active immutable plan or repurpose an old attempt.
No database/schema migration or customer balance rollback applies.
