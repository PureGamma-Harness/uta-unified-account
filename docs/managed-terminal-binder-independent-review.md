# Independent review of the staged terminal binder

Candidate `8a0aa6893d7ad301e1b67379a893e31554ca52c2`, core `2a9d9a8a35bd9676494cb4b9af164a6ee6611861`. **NO_GO pending correction of six first independent counterexamples.** `REVIEW_AUTHORIZED=False`, candidate eligibility and every financial/production flag remained false throughout this review.

The first extractor review `bc478063a8f3e911ff00403525fff24678154f99` remains unchanged. Stage one now keeps its candidate flag unconditionally false. Stage two adds a separate metadata binder; it does not execute another audit.

## Execution and independence

One new independent challenge ran on CPU 3 with a ten-second subprocess bound. It completed in **132,971,886 ns**, exit 1, empty stderr: **17 cases, 11 pass and six red**. [Original result](../evidence/reviews/managed-terminal-binder-independent-20261117/first.stdout.json), [execution record](../evidence/reviews/managed-terminal-binder-independent-20261117/first-execution.json) and [challenge](../evidence/reviews/managed-terminal-binder-independent-20261117/first_independent_challenge.py) are retained.

To keep the complete fixture aligned with the author's actual-schema positive example, the challenge imported the author's synthetic-chain builder without running its 12 tests. Mutations, expected refusals, file-based manifest negative controls and result collection were independent. This does not claim a second independent construction of the whole complete positive chain.

Only fixed Git code and newly generated temporary synthetic JSON were read. No running task directory, database, clone, process observation, signal, observer, native worker, audit, full replay or financial operation was accessed. The reviewed source tree was not modified. No red case was rerun.

## Six counterexamples

| Counterexample | Actual result | Required result |
|---|---|---|
| Before/after `unresolved_steps=False` and `unresolved_faults=False` | metadata_chain_bound=true | Refuse Boolean counts |
| Before/after planned/completed counts `5400.0` | metadata_chain_bound=true | Refuse floating counts |
| Progress and matching producer response planned count `5400.0` | metadata_chain_bound=true | Refuse floating counts |
| Summary expected/actual fault counters `180.0/18.0` | metadata_chain_bound=true | Refuse floating counts |
| Before child reuses the producer's exact PID/birth pair, with its existing later start/end times | metadata_chain_bound=true | Refuse one process identity representing two separately spawned children |
| Elapsed seconds represented by a 1,001-digit integer, also copied into the matching producer response | OverflowError escapes | Return a fixed structured mismatch/error result |

The first four arise from Python numeric equality: `False == 0` and `5400.0 == 5400`. Some other counters are already checked with exact integer types, so these remaining fields are inconsistent with the intended strict schema.

The identity case preserves terminal start/end ordering and individual identity-field shapes. A PID may be reused after exit with a different birth token; the identical PID/birth token cannot represent two distinct children. Check pairwise uniqueness of the four actual spawned child identities without banning valid PID reuse with a new birth.

The numeric case stays far below each JSON byte cap and Python's integer-text parsing limit. `number()` calls `math.isfinite()` on an unbounded integer, which raises `OverflowError`. Reject unsupported magnitudes/types before float conversion or catch the conversion failure and return the fixed structured refusal. This is an evidence-tool availability/contract failure, not a demonstrated trading attack.

## Corrected earlier gaps and passing boundaries

The independently adapted failed-cold-receipt, changed after-watermark and contradictory fault-count cases are now refused. Missing files, a file digest mismatch, a wrong externally supplied manifest hash, duplicate JSON keys and an extra manifest path are all refused. Boolean fault generations are refused.

A noncontract ordinary file in the temporary bundle was ignored and its synthetic sentinel was not echoed. The manifest is an exact eleven-path allowlist, not a whole-directory integrity scan. A trusted outer directory and externally authenticated reviewed manifest digest remain explicit preconditions. Extra files are not made authoritative by this tool.

The schema-shaped positive chain remained bound while candidate and production flags remained false. This is a narrow metadata-consistency result only.

## Static observations and limits

The code now checks the original boot/start/deadline/source contract, exact workload, producer/launch identity, child exit and complete-output declarations, ordering, before/after watermarks, receipt audit hash/runtime/scope, financial counts and reopen/log declarations, exact fault plan and summary/coverage consistency. Before legitimately permits only the missing-cold-receipt condition; after requires the receipt-backed eligible state.

These checks validate recorded declarations. They do not independently reobserve a stopped process, read journal bodies, replay every financial event or recompute risk. In particular, child stdout hashes are shape checked and externally pinned along with their wrapper JSON; filtered `response` cannot generally reproduce the original raw stdout hash. Do not claim that this binder independently authenticated raw child stdout, all journal segments, process existence or financial audit execution.

The imported positive fixture uses schematic timestamps; its physical process lifetimes and complete real-task chronology were not independently established by this challenge. This review does not broaden schema-shaped synthetic data into actual six-hour evidence. Actual terminal sealing remains owned by the original supervisor and requires a separate root authorization after natural collection finishes.

## Correction, deployment and rollback

Preserve these original results and the author's first twelve passing pure cases. Correct the exact remaining count types, pairwise child identity invariant and bounded numeric conversion with fixed error codes. Add a separately labeled corrected-source validation; do not rerun the running task or overwrite red evidence.

The stage-one extractor and stage-two authorization must remain fail closed. This review changes only evidence/documentation and authorizes no deployment. Reverting its commit removes this report while keeping original raw records. No schema, API, service, parameter, fund ownership or active task was changed.
