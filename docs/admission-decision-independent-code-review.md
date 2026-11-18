# Independent admission-replay CODE review

Source `8be1838b04224d43c348a86030471c8e4051e0b6`, metadata OWN
`90ba4beda98e9bc1a58bb64a5345db91c64f6906`, is **NOT CLOSED** because of
one supported-control validation gap. This is static analysis, NOT_RUN with
zero reviewer target imports, compilation, tests, SQL, native probes or child
agents. No test result or production incident is inferred.

Findings bind the immutable source above. Final status showed the author
preparing newer WIP; that fix and its forthcoming selectors are not reviewed
or authorized by this record. No additional specific blocker was found within
the original bounded review scope.

## Required correction: RO control shape

`DecisionAudit._replay_admission` checks `before["halted"] is False` only in
the ordinary branch at `uta/decision_audit.py:538`. The RO branch at lines
531-536 checks quantity allocation and surplus, but never validates the halt
value's native boolean shape. The ordinary `unrelated_state_unchanged` check
merely compares before with after. Numerical valuation ignores halt values.

Consequently the existing otherwise-valid RO example can have both archived
halt values replaced by `1` or `"unknown"` without changing any calculated
predicate: the new helper can still return VERIFIED. Real admission always
calls `_halted` at `service.py:785`, including RO; the producer's representation
is a boolean and a damaged control is rejected. This is a false-verification
gap for malformed evidence, not an observed illegal financial admission.

Require native boolean halt shape for both branches before evaluating their
different permissions. Preserve legitimate RO with `halted=True`. Add a pure
negative that changes *both* before and after halt values, plus a positive RO
True control. Existing ordinary tamper coverage changes only before and can
fail through unrelated-state mismatch, so it does not close this case.

## Existing-policy compatibility remains OPEN

The new `admission_contract` policy field creates a new content-addressed
policy even when all financial settings and cache options are unchanged.
`existing_services._source_arguments:255-269` filters old/new policies by those
financial fields, ignores the contract and appends both candidates. Preserving
an old policy while registering the new policy can therefore produce two
candidates and `existing base policy is missing or ambiguous` on existing
read-only reopen. New authorities have one candidate and are unaffected.

This must be explicitly accepted as a deployment restriction or separately
fixed/verified before claiming preserved-history handoff compatibility. A
focused check should include old-without-contract plus new-with-contract
policies having identical constructor arguments. Deduplicating identical
arguments or selecting the exact current contract must retain refusal of
genuinely ambiguous economic/cache configurations and the exact current
policy/artifact checks at lines209-217. Do not delete old policies, rewrite
artifacts or add a compatible-math engine bypass.

## Positive static findings and proposed validation

All64 manifest entries total1,316,614 bytes and equal physical regular files,
declared SHA-256 values and frozen Git blobs. Manifest SHA-256 is
`8b5cb9cc33ceb902ef434aab864d04e4c1d40216e41a780947877b2b160e7c26`.
Restoring only the capture/import/fee-variable edits reproduces the complete
base service AST (`fc2d574d7ac434a214bf332649edf0d2effc2a8c`). Existing SQL,
financial guards, known-ID early returns and RO behavior remain intact.
The ordinary fee is still evaluated once and no risk revaluation is added.

The new projection independently implements rational signed-cost settlement,
PnL flooring and full-order fee ceiling. Hand examples for MM equality, legal
IM equality, old-order reserve, underwater RO, overlapping RO, adverse RO,
carried negative cost dust, a flip and a short close are consistent. It never
calls service admission/projection/fee/guard helpers. Risk/reserve valuation
still reuses `_replay_state` and the existing reserve engine: these are not
independent numerical oracles. Source/policy/market references remain the
outer replay prerequisites; local unsigned consistency is not authentication
against a database owner who can replace a coherent archive and its guards.

The capture stays inside the existing financial transaction. Audit serialization
or record failure propagates through the existing rollback path; no swallowing
or early commit is added. This still needs an actual audit-write-fault rollback
check before a broad durable-transaction acceptance claim. Schema3/format1 and
old immutable archives are unchanged. Top-level matches remains valuation-only;
admission status is separate. Missing evidence, unsupported contracts and FILL
must remain UNSUPPORTED, never acquire reconstructed permission.

The6 pure and3 SQL selectors identify direct TestCase classes, with no inherited
case expansion. Static imports/globals and original staticmethod descriptors
are present; no source-extraction annotation/descriptor omission is apparent.
Pure import does passively load sqlite3 via decision_audit/storage: a future
guard must distinguish library import from forbidden actual connect/SQL.
Additional small negatives should remove the policy contract, use an unknown
contract, and exercise consistent before/after control tampering. Keep manual
expected values independent of the producer. Existing numerical/audit-fault
regressions and old/new-policy coexistence require separate bounded scope.

There is no bounded once launcher yet; the plan explicitly grants no GO.
Exact-source closure, raw caps, runtime identity, actual caller exit/reap and
separate SQL authorization remain prerequisites. Old code-bound authorities
cannot be hot-swapped to this binary. Retain matching old releases for old
artifacts and preserve all receipts, orders, fills and policy history on
handoff/rollback. Freshness, fencing, API identity, rejection archives,
arbitrary concurrent partial-fill guarantees, capacity and production remain
unsupported. This independent worktree changes only its own safe review files.
