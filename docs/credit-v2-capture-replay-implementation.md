# Dedicated credit capture and replay implementation slice

This slice implements the dedicated `CreditAuditV2` capture, same-connection
staged verifier and archive bundle replay. It does not publish a capability,
acquire a writer, wire public borrowing or claim an executed V2 loan. Missing
native lifecycle/FIFO/loaded-code dependencies still fail closed. The first
`NATIVE_PREPARED` format remains permanently unable to execute credit.

The retained contract is `credit-v2-payload-contract.md`. Capture checks actual
native intent and source rows, original market snapshot, policy and code
archives, gross assets/cash deficits/principal/interest, pool funding, immutable
allocation, actual pre/post account versions and all four ordered journal legs.
The operation replay reconstructs both complete risk results and the credit
transition; it does not substitute generic margin replay for borrowing replay.
Selection, final price validation and recording are actual exchange clock
observations. Physical COMMIT time is explicitly null. Staged verification
rechecks actual source, intent, financial state, original receipt and inbox
terminal rows; a valid payload alone cannot establish durable execution.

`evidence/runs/credit-v2-dedicated-risk-build` retains the initial fixture error
(the test had not initialized its inbox parent) as well as its targeted repair.
The preseal helper/risk/journal/policy checks are component evidence. The two new
actual missing-context/constructed-capture negatives passed on Python 3.10,
3.12 and 3.13 in the `context-negative` subdirectory. They establish no financial
grant from observation objects. They do not exercise the still-closed positive
V2 capture or claim independent financial signoff.

Deployment at this slice is code-only with the default closed. No CLI flag,
route, automatic migration or promotion is provided. Rollback before any V2
publication is ordinary binary rollback after confirming no V2 marker exists.
A future published V2 authority must use its exact retained code and complete
native loader; older binaries must reject it, rather than delete a marker or
rebuild history. Positive execution, strict reopen/restart, actual old-binary
inventory refusal and the independent integer oracle must all pass in a later
slice before this internal synthetic scope can be accepted. HMAC first source,
lending distress/insurance/ADL and real-funds approval remain outside this slice.

The dedicated policy loader also validates the mandatory original base audit
capability/guard inventory. A complete dedicated policy archive cannot mask a
removed base market-history guard. An actual temporary-database negative and
complete-archive control passed in 0.124s; see
`evidence/runs/credit-v2-base-audit-dependency`. This is an additional V2 load
dependency, not a change to any frozen M2 tree.
