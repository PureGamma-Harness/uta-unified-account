# Credit identity and the private lease-observation tag

The frozen834ad6e source completed its unique first six-method in-memory run:
PASS_LIMITED_PURE_ONLY, zero failures/errors/skips, actual host and outer exit0
and reap, complete EOF/END and timely TAIL. Independent RAW review is pending.
[First evidence](../evidence/reviews/credit-observation-tag/first-834ad6e/README.md)
retains the separate source/host/raw bindings and limits. This result does not
authorize financial activity, recovery, whole-CI acceptance, or production.
The change's base is published PR42 source
`f510bf5fea852ca04c87930077861c312320141f`.

## Problem, evidence, and uncertainty

The first captured PR42 push Python3.10 and3.12 unit bundles each report2102
tests, zero failures and25 errors. Their captured credit-identity traceback
reaches `_loaded_modules`' uppercase module-constant scan and `_static`'s
`unsupported loaded financial constant type` error. The first CI did not retain
the failing module attribute. No later calculation can fill that historical
telemetry gap or prove every error had a single cause.

A static comparison identifies a concrete incompatible new binding:
`uta.writer_fence._LEASE_OBSERVATION_TAG = object()`. Its name matches the
existing uppercase-constant scan, it is outside the unchanged finite live-state
exclusion list, and `_static` rejects a plain object. The other new observation
constants contain supported primitive/container types. The focused tests are
designed to establish this conditional path on a separately frozen source. The
first834ad6e focused run passed those methods; the original CI's telemetry gap
remains unchanged.

## Local rule and implementation

Local rule `CREDIT-TAG-001`: a private diagnostic source marker must preserve
identity comparison while having a finite reviewed structural representation in
the already established credit-code identity contract. This is an internal
compatibility rule, not a Bybit/Binance rule or proof of their behavior.

The marker becomes `_LeaseObservationTag.V1`, a private Enum singleton with
value `uta_lease_observation_v1`. All original `is` checks, tuple/MappingProxyType
requirements, exception-identity preservation and publication allowlists remain
unchanged. An existing unknown or old-object-tagged exception attribute stays
unknown and untouched. The producer does not upgrade historical capsules.

The existing serializer already records Enum module/type, member name and value.
It also records the Enum member as a class constant and the class's loaded code.
The marker and its complete source stay part of the artifact; no name is added
to `_LIVE_GLOBALS` and no unknown-object serializer is introduced.
`uta/credit_artifact.py`, its format and parser, required-function checks,
source/runtime checks, and the full exclusion contract remain byte-for-byte
unchanged. Arbitrary module objects and unsupported financial code constants
still fail closed.

The marker identifies in-process diagnostic provenance only. Code in this
trusted process can access the private module, so the marker grants no financial
authority or isolation against plugins, the service OS user, or arbitrary code.

## Focused verification plan

The six selected methods have twenty-two bounded source cases:

| Test | Independent expectation |
| --- | --- |
| `test_complete_artifact_includes_tag_member_and_loaded_class_code` | Complete current artifact and validator include the exact Enum descriptor, member, loaded class code and original exclusions; its entire source map equals61 retained pins, added/missing source maps reject, activation remains false |
| `test_unsupported_objects_and_financial_code_constants_still_reject` | Plain object, patched tag object, unrelated uppercase object and unsupported financial code constant all reject |
| `test_enum_value_and_same_value_other_type_change_loaded_identity` | Changing either the value or Enum type changes the constant fingerprint; test mutations restore |
| `test_unknown_existing_payload_sources_are_never_upgraded_or_published` | Six old/wrong tag or tuple/mapping shapes remain untouched and unpublishable |
| `test_original_error_and_native_typed_observation_filter_are_preserved` | Original error/args/code/cause survive; exact manually listed primitives publish and synthetic nonce/aliases/negative fields do not |
| `test_publication_filter_keeps_original_rejection_of_aliases_and_unknown_fields` | Six invalid typed/unknown fields remain excluded by the original publication predicates |

Expected Enum descriptors, exclusions, filtered fields and rejection cases are
hand recorded. The real current `credit_code_artifact` and its validator execute
in memory, covering the whole artifact rather than only a direct `_static`
call. The actual validation predicates are selected from the unchanged pinned
source AST; the validation process runner is never imported or invoked.
The expected complete source map comes from the retained plan inputs, not from
the production artifact function. The focused control guards and its resulting
loaded identity do not qualify an uninstrumented financial writer.

`evidence/reviews/credit-observation-tag/once-plan.json` binds65 inputs:61 UTA
Python sources, the test, inner and outer entries, and the unchanged validation
source. The fixed outer entry verifies their Git and physical bytes plus actual
source HEAD and the approved plan SHA. Its retained SHA-bound capsule supplies
every target compilation/import; later physical reads are checks only.

The independent CODE review found that the7030d121 preparation checked only one
artifact source digest and its inner `dup2` sent native output around caller
pipes. That preparation and exact2e9c9a91 plan remain NOT_RUN/zero attempts,
never RED, in Git and the retained `once-plan-7030d121-NOT_RUN.json` copy.
The revised complete-map check and fixed parent-captured mode close the proposed
CODE gaps; they require independent review before any execution.

The fixed outer entry is `tools/run_credit_observation_tag_outer_once.py`. It
binds CPU1, then owns one new timeout/taskset interpreter with hard KILL20seconds
and at most two seconds for pipe drain/reap/completion checks. The inner requires
`--parent-captured-stdio` plus the verified injected capsule and never redirects
FD1/2. All native and Python target/bootstrap/taskset/timeout output reaches the
parent selector through two pipes. Shared256KiB capacity includes a512byte
trailer reserve; the parent charges before each single FD write. A short write
or overflow is sticky125 with no refund, continuation or later payload.

Fresh output is0700 with O_EXCL0600 files. Complete inner END, both pipe EOFs,
actual host wait/reap/exit0, complete source post-checks, no cap failure and a
timely outer completion are all necessary. The caller must still observe actual
outer process exit: an earlier END cannot attest that future event. Late final
receipt publication returns126/UNKNOWN even if an earlier record existed.
Source/Git preparation is separately visible and never credited as test time.

No SQL connect, application subprocess, worker thread, network, old PID/proc
operation or archived-code execution is permitted. Imports and runtime metadata
are allowed; only the parent's new timeout/interpreter and read-only Git
preparation are orchestration processes. The caller separately retains literal
outer argv, first launcher streams, actual outer exit/reap and elapsed time.
Missing receipts, timeout, drift, or incomplete output remain UNKNOWN. This is a
reviewed trusted-source guard, not an OS sandbox. Twenty-two cases are source
bounds; actual method/subcase observations must be reported separately.

## Deployment, compatibility, and rollback

There is no SQL/schema/data migration or customer API change. This source changes
code identity, so a future synthetic deployment must use its own fresh artifact
and authority layout after independent review and CI. Never hot-swap an existing
code-bound authority or rewrite an activation marker. Old retained artifact IDs
keep the same format and exclusion contract; they cannot claim to describe the
new source as current. Historical artifact data never selects executable code.

Before rollout, preserve the previous immutable image, exact source/runtime
binding, commands, fills and ledger evidence. Stop the synthetic writer, verify
its termination, then restore only a compatible previously accepted image and
layout. Reverting just this patch to PR42 source `f510bf5` returns to a known
unsupported-tag candidate and is not an accepted service rollback. The earlier
PR38 source is also not a production approval. Preserve all confirmed effects
and UNKNOWN command IDs; never erase state or resubmit effects under new IDs.

First CI failures remain failures. New focused results, any future CI, native
recovery and production acceptance are separate gates and require their own
source-specific evidence.
