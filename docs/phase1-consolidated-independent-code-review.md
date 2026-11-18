# Independent consolidated source review

The reviewed financial source is `f6f27524f395d0aa2ca3e96e70269be36086f189`, pinned from the integration worktree before review. Supplemental documentation is pinned separately at `1e0a9e62677ddb867b5a47e5b3cdaa4314fa3732`; the inventory correction is `d1fd381bde923dc4010977058b76e34d6162e9a9`. Both supplements leave every runtime file unchanged. This independent report commit is based on the original source pin; it does not substitute a later checkout for that source.

The limited source gate is **accepted for proceeding to the first integrated CI**, including the inventory correction. Functional, installed-component, performance, recovery and production acceptance remain pending. Historical branch CI establishes no combined-tree result. No target imports, compilation, financial execution, SQL, workers, PID inspection/control, CI runs, downloads or benchmarks were performed in this review.

## Origin and preservation

The accompanying [static evidence](../evidence/reviews/phase1-consolidated-independent/static-code-evidence.json) retains full public source pins, byte lengths, Git blobs and independently recomputed SHA-256 values. All 19 designated file comparisons are exact:

| Source | Files preserved |
| --- | --- |
| PR49 | `ledger.py`, `startup.py`, `writer_fence.py` |
| PR52 | `service.py`, `decision_audit.py`, `credit_audit_v2.py` |
| PR53 | `funding_local.py`, `funding_obligations.py`, `perpetual_funding.py` |
| PR51 | `cross_decimal_kernel.py` |
| PR55 | the independent oracle and six-case oracle test source |
| PR54 | monitor failure helper, original process test, helper tests and two bounded capture tools |
| PR56 | process-readiness and startup-contention test diagnostics |

All seven public input pins are actual ancestors. The three separately supplied excluded nonpublic lineage objects exist locally and are not ancestors; their private identifiers are omitted from public evidence. Relative to PR49, runtime changes are exactly three modified audit/service files and four added Python modules. No workflow changed. The documentation manifest matches every tracked runtime file: **65 Python modules plus one HTML file, 1,456,126 bytes**, with exact path set, size, SHA-256 and Git blob for all 66 entries. This is source identity evidence only.

## Integration defect found and corrected

At the original source pin, `test_credit_lease_observation_tag.py` retained the explicit 62-module PR51 inventory and `len(retained) == 62`. Its ordinary snapshot helper compares that tuple to every deployed Python file. The combined source has 65 modules, so the predicates were structurally inconsistent. This finding was made from source; no failing execution is claimed.

The supplemental correction preserves the original V2 tuple and declares V3 by explicitly adding the three funding module names. Static AST inspection confirms 65 unique names exactly equal the Git runtime set. Both the exact-set comparison and fixed-count assertion remain strict. The allowlist is not derived from the files being checked. This closes this source defect only. Historical frozen validation must continue using its retained source, test bytes and pins; passing old pins into a current test is not historical replay.

## Default behavior and policy contracts

The service still imports and calls `portfolio.calculate_cross_risk`; no runtime module imports `cross_decimal_kernel`. The new funding import edges occur only within the optional funding modules. Neither service, CLI, routing nor startup registers a new funding or calculator path. Both funding capabilities require explicit fresh synthetic installation, reject managed/code-bound services, and reject coexistence with the other funding schema. Source presence grants no capability.

The valuation policy declares exactly the existing ten `BASE_POLICY_FIELDS`. The order envelope adds only the eleventh `admission_contract` field. Internal credit consumes `valuation_policy`, canonicalizes the fee as before, and retains exact equality with the persisted credit policy. The four dedicated contract tests remain present, including changed/unknown field rejection. Audit admission evidence remains separately scoped from numerical valuation; neither result proves historical authorization, lease ownership or arbitrary concurrent fill safety.

The PR54 process failure hook retains the original assertions, timeout and rethrow. PR56 retains readiness and contention success predicates, adds finite observations, and does not lengthen their waits. Observation overhead can affect timing. Successful runs cannot establish that a native failure branch or an old intermittent cause was exercised.

## Remaining interaction risks and required acceptance

1. **Source and policy identity across upgrades.** Adding modules changes whole-runtime artifact identity. Unchanged schema numbers do not authorize opening a database pinned to a branch artifact. Keep old-authority fail-closed checks, and verify a fresh combined authority, exact-code reopen, changed-code rejection, policy replay and fencing together. There is no existing-authority migration acceptance here.
2. **Pending funding exposure.** A scheduled debit is still not an admission, withdrawal or transfer hold. Managed integration is expressly rejected. Production scheduling must remain disabled until unified encumbrance, capital shortage, concurrent order/fill/cash movement and recovery are independently tested. Local arithmetic/apply success cannot close this gap.
3. **Candidate identity and authority.** The decimal calculator is opt-in; source hashing does not prove its loaded-callable identity. Keep the reference authority until loaded-engine binding, shadow comparison and unsupported-domain rejection are reviewed and executed. The six synthetic oracle groups do not establish exchange PM or model calibration.
4. **Readiness, lease and publication.** Byte preservation does not resolve native timing failures, publication-barrier liveness or cancellation/repayment priority. The original process/readiness/startup tests must run on this integrated artifact, retaining first failures and bounded observations. Do not infer causes or repair a failure by selecting a later green run.
5. **Packaging and execution.** The source inventory and automatic package configuration are consistent, but no wheel was built or installed here. Exact wheel/sdist bytes, installed imports and functional calls are distinct evidence. The existing installed CLI protocol does not itself establish execution of the newly added optional funding/calculator paths.

The first normal integrated CI must execute the full discovered suite on Python 3.10–3.13 and preserve its original results, demo/acceptance, formal models, archive equality and isolated installed-package results. Explicitly inspect these integration-sensitive tests in those results:

- `test_credit_lease_observation_tag.py`; `test_admission_credit_policy_contract.py`; `test_decision_admission_capture.py`; credit audit helper, runtime-chain, restart, legacy/lease and code-binding tests.
- Both funding test files, especially schedule/apply/reopen, stale data, capital proofs, competing claims, clock regression, post-cut fills, unknown replies, code binding and old-capability rejection.
- Decimal kernel and enumeration tests plus all six independent oracle groups; preserve the original synthetic golden bytes rather than regenerate expected results from the candidate.
- Ledger guard/sequence/catalogue tests; writer-fence and owned-startup tests; original durable-process, process-readiness and startup-contention tests; bounded diagnostic helper tests.

Installed testing for any claim about optional components must actually import and invoke those components from the installed artifact, outside the source tree, and distinguish that coverage from package byte equality. Further matching-to-ledger reconciliation, fault/restart recovery, sustained open-loop order and liquidation capacity, liquidity limits, multi-node recovery and explicit real-funds approval remain separate release gates. No production or real-funds approval is issued.

## Review reproduction and rollback boundary

Reproduce static checks with immutable `git show <pin>:<path>`, `git ls-tree -r`, blob/SHA-256 comparisons, `git merge-base --is-ancestor`, and AST parsing without imports. The evidence records the exact comparison set and results. The report and evidence are administrative additions; reverting them changes no financial runtime or schema. Deployment and rollback instructions in the supplemental delivery document correctly limit this candidate to isolated synthetic namespaces and require preserving/reconciling confirmed effects before any authority handover. They are instructions, not an executed deployment or rollback result.
