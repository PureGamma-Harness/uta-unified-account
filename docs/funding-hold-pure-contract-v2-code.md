# Pure funding hold: contract-v2 implementation candidate

This candidate implements the integration-owner decision 2bb8095f, pending its
independent policy and source reviews. The historical 4e2b implementation and
7519ace0 independent limited-subset review remain unchanged. This is a pure
USD-only data model, with activation_permission=false and no service hook.

advance_stage now requires expected_revision and an exact complete
expected_active_stage. It validates the expected stage's duty/rule links and
compares every Stage field before returning a replacement. The prior keyword
expected_active_ref is unsupported. Referenced content and supplied history
still require authoritative authentication and atomic persistence in D2.

preview_wait first computes the proposed non-revision fields. An unchanged
record returns the original object and revision, in WAIT or DEFAULT_REVIEW;
a changed record increments exactly once with checked overflow. Deadline
equality, sticky default, query spacing, last permitted query and no refund for
unknown dispatch remain unchanged. No clock, actual query or cancellation is
performed. Policy and action hash algorithms are unchanged.

The original 22 tests retain their existing expected financial values; eight
stage callsites are changed to the new complete precondition. Seven additional
test definitions cover stale exposure/amount/kind, foreign or legacy expected
inputs, normal/default no-ops, changed versus unchanged revision exhaustion,
interval/deadline equality, exact revision increments and duplicate root action
budgets across scales. All 29 tests are NOT_RUN at this source freeze.

The explicit source inventory advances to V4=V3+funding_hold_pure.py, 66 Python
files plus the HTML runtime asset. V2 and V3 retain their original lists. The
new inventory is a literal allowlist, not derived from the directory it checks.
No original 66 runtime file is changed; only the new pure module is revised.

## Delivery and acceptance

No data migration or activation is performed. After policy and source reviews,
run a separate first normal multi-version CI on the exact public source. The
independent reference must implement the adopted contract itself; full-field
differential testing remains a separate unrun gate. Unit values do not prove
complete-history ownership, shared global budgets, durable CAS, outbox, real
ACK, restarts, admission/withdrawal/transfer coverage or financial settlement.
Those D2 gates remain BLOCKED. Capacity, HA and real-funds production are NO_GO.

Rollback removes the new pure module/tests, restores the explicit previous
inventory and reverts these new contract files on a fresh engineering authority.
Do not rewrite existing funding obligations, confirmed trades or journals.
Before any later service integration rollback, preserve and reconcile confirmed
effects; constructing a new WaitRecord never authorizes a fresh global budget.
