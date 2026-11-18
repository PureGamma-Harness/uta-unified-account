# Linear admission evidence v1

Status: CODE_ONLY, NOT_RUN. This branch starts at PR46 source
`fc2d574d7ac434a214bf332649edf0d2effc2a8c`. No target import, compilation,
SQL, worker, benchmark or CI run was performed to prepare this change.
Independent CODE review and a separately authorized first execution are required.

## Contract and compatibility

Audit-enabled `ORDER_ACCEPTED` records now retain the already evaluated full
order projection for ordinary and reduce-only orders. Their summary includes
`admission.format=1`, contract `UTA-LINEAR-ADMISSION-v1`, projected realized
PnL and full-order fee. The policy identifies the same contract. Existing
outer market, rule/policy, source artifact, account version and business-ID
references remain authoritative. The new evidence is written in the original
financial transaction; a failed audit write still aborts that transaction.
No additional risk calculation or financial predicate is added by this patch.

The archived JSON payload gains fields; trading schema3 and archive format1
are unchanged. No table migration, backfill or automatic repair is introduced.
The unsigned code-bound artifact changes. Old releases remain necessary for
their own archived artifacts: the existing exact engine/runtime mismatch check
still runs before valuation and has no compatibility bypass.

Unchanged schema does **not** imply existing-authority compatibility. This
delivery supports fresh synthetic authorities only; migration of an existing
audited authority is not implemented or accepted. The policy gains a contract
field, so an old no-contract policy and the new policy have different IDs even
when their financial configuration and execution options are identical.
`existing_services._source_arguments` does not distinguish that field or
deduplicate equal execution options: both rows are candidates and read-source
reconstruction rejects the ambiguity. This patch deliberately leaves that
rejection and exact archived-policy/current-artifact checks unchanged.
Do not call the ordinary installing constructor on an old archive as a migration:
it may append new metadata without proving read-reopen compatibility. No old
policy is deleted, rewritten or selected by a compatible-math bypass. Old/new
policy coexistence and existing-authority writer handoff remain OPEN.

`DecisionAudit.replay` preserves `matches` and `differences` as the existing
numerical-valuation result, including the proposed reserve. The additive
`valuation_matches` states that meaning explicitly. The separate `admission`
object reports:

| status | eligible / matches | meaning |
| --- | --- | --- |
| VERIFIED | true / true | All supported recorded financial checks pass and evidence agrees |
| FAILED | false or null, or a mismatching projection | A predicate/evidence check fails, or evidence is invalid |
| UNSUPPORTED | null / null | No supported contract/evidence, or a different decision kind |

`eligible` concerns the replayed supported financial checks. A replayed eligible
account with a recorded projection mismatch still has `matches=false` and
`status=FAILED`. Callers must not treat top-level `matches=true` as admission
acceptance. Old records without admission evidence remain UNSUPPORTED even if
their numerical valuation matches. Unknown contract versions also remain
UNSUPPORTED; no current price or rule is used to fill historical gaps.

## Supported checks and limits

The admission checker independently derives settlement projection, USD fee
ceiling, realized-PnL floor and surviving-cost dust using exact rational
arithmetic. It never calls `ExchangeService._admit_order`, `_project_fill`,
`_fee` or the production admission guards. It then uses the existing numerical
replay calculator to value that derived account. Consequently this is an
independent admission/settlement derivation, **not** an independent reference
implementation of Cross risk or reserve valuation.

Supported checks include one USD-settled multiplier-one linear limit order,
native input/position bounds, live-order limit, existing-order reserve,
new-order identity and account-version increment, unchanged unrelated state,
recorded halt/liquidation controls, configured product status/steps/minimum,
rule/catalog/market provenance, full-order projected fee/PnL, ordinary IM
reservation and strictly positive projected MM surplus. Reduce-only checks
separately retain cumulative outstanding reduction quantity and non-worsening
maintenance surplus; they do not inherit the ordinary IM/MM rule. Both paths
require the captured pre/post halt states to be native booleans. In RO mode,
`halted=True` remains valid; corrupt control types are invalid regardless of
whether equal values appear in both snapshots.

This does not certify historical clock freshness, writer fencing, API identity,
command delivery, matching, rejected-command history, or correctness under all
concurrent orders and arbitrary partial-fill sequences. It does not resubmit a
command. Fill decisions retain numerical replay but have admission UNSUPPORTED.
Known-ID lookup still returns the original receipt before new admission checks;
the patch neither generates a second decision nor changes historical evidence.

## Manual examples and proposed verification

All examples use synthetic USD, mark/limit100, multiplier1, fee0.0004 and IM0.1
unless stated. Expected values are constants, not outputs of service helpers.

| case | hand calculation | expected |
| --- | --- | --- |
| MM equality | cash10.04 - fee0.04 = equity10; MM10 | reject ordinary |
| lower MM | same equity10, IM10, MM5; available IM0 | accept ordinary |
| fee shortfall | cash10.03 < IM10 + fee0.04 | reject ordinary |
| two outstanding orders | cash20.08; old reserve10.04; new reserve10.04 | accept, retain both reserves |
| reduce-only underwater | cash4, position1@100, MM5; close1 costs0.04; surplus -1 becomes3.96 | permit reduction |
| overlapping reductions | position1; outstanding reduction0.5 plus proposed1 | reject overlap |
| unsafe reduction | cash4; close0.5 at90 realizes-5 and fee0.02; projected surplus-3.52 < -1 | reject reduction |
| carried dust | position0.3 cost0.003; sell0.2 at0.009; PnL-0.0002 floors to-0.01 | surviving cost-0.0088 |
| flip | long1 cost100; sell2 at90; PnL-10, fee0.08 | short1 cost-90, cash89.92 from100 |
| short close | short1 cost-100; buy0.5 at90; PnL5, fee0.02 | short0.5 cost-50, cash104.98 from100 |

The corrected pure plan selects seven methods in
`tests/test_admission_policy_reference.py`. Four methods in
`tests/test_decision_admission_capture.py` propose four fresh temporary local
SQL authorities, one local `apply_fill` call and no paired matcher/native
worker. They must not be called real matching throughput acceptance. Proposed
SQL checks cover ordinary capture, exact-MM rejection with no accepted record,
original-ID retry while halted/stale, configured rule references, one RO
admission, explicit unsupported fill-admission scope, and source-argument
rejection when a synthetic negative fixture has old/new policy candidates.
The last case does not establish complete `open_existing_services` compatibility.
Source/code binding,
raw-output closure, before/after hashes and actual caller exit/reap must be
sealed by the eventual execution protocol. Until that review and run, every
case remains NOT_RUN.

## Independent CODE corrections before any execution

The initial CODE delivery `90ba4beda98e9bc1a58bb64a5345db91c64f6906`
and its six-pure/three-SQL plan remain in Git as NOT_RUN, zero attempts.
Independent source review identified a replay false-verification path: in RO
mode, changing both captured halt states to a nonboolean could satisfy the
old unchanged-state comparison while skipping the ordinary-only control
predicate. The real service validates the control row before either branch.
The correction requires native booleans in both snapshots without rejecting
RO when the actual boolean is True. This is a static verification gap, not an
observed illegal order admission or an executed failing test.

The original independent report is
[`a9ac9cf2928f635cbfd5da6a7c31e071938204e1`](admission-decision-independent-code-review.md).
Its `ADMISSION-RO-HALT-SHAPE-001` finding and NOT_CLOSED verdict remain bound
to the original source; this author correction does not close its independent
gate without a separate delta review.

The same review identified the policy-coexistence ambiguity described above.
This delivery chooses the explicit fresh-only scope and a synthetic rejection
test; it does not change the existing reconstruction algorithm or introduce
an authority migration. Original plan/manifests are retained separately when
the corrected source is frozen. All proposed new cases still require review
and a bounded execution entrypoint before any GO.

## Deployment and rollback

Keep audit mode opt-in and deploy only to fresh synthetic, code-bound
authorities. Do not modify a live authority or binary in place. Existing audited
deployments have no supported migration or writer-handoff path in this change;
that work requires its own compatibility design and independent acceptance.
Preserve all original command IDs, receipts, orders, fills, immutable audit
rows and old policy/source versions. No experiment on an existing authority
is part of this CODE delivery.

Rollback must use a compatible audited release after quiescing admission and
verifying writer ownership. Preserve the additional JSON evidence and old
release artifacts. No downgrade of schema, deletion of records or inferred
reconstruction is supported. An older release cannot authoritatively replay
this release's artifact; use its retained matching source/runtime. Measure the
additional ordinary projection capture size and replay work before capacity
claims. No production, PM, real-funds or full admission guarantee is accepted.
