# Independent pending-funding rule review

Reviewed specification: `bac842516abc8f1e8af42f8624b5cf28f31b5972`, parent `92979e9b2cd719bfaa9d857e13c2b99239355330`. This is a separate review from market-publication queue changes. The four-file patch changes documentation/data only. Its 13 source pins match immutable Git bytes, blob IDs and SHA-256 values exactly.

The core financial policy and the numerical examples are coherent within the stated USD-at-par Cross domain. **Complete specification signoff is withheld for two rule definitions below.** The documents may remain a proposed design; they authorize no financial entry point. No UTA module was imported, compiled or executed; no SQL, process, worker, CI, fault test or production calculator was used.

## Independent numerical evidence

[Arithmetic and source evidence](../evidence/reviews/pending-funding-risk-hold-independent/arithmetic-and-source-review.json) records independent standard-library `Fraction` calculations from raw decimal strings. All 17 examples were checked, including 123 explicit numeric-field comparisons, four-step payment/receipt and correction sequences, permitted/forbidden atomic-state arithmetic, and rounding-capital conservation. The state-transition assertions in these examples remain proposals; calculating their values does not execute leases, persistence, authorization or crash recovery.

The traceability contains 22 rules, nine invariants and 24 acceptance gates; all rule references resolve to declared cases/gates, and all 24 gates remain `NOT_RUN`. Original proposed status and pending signatures have not been rewritten.

| Constraint | Independent result |
| --- | --- |
| Gross funding | `H=P+U`; pending receiver `N` never offsets H, including opposite tasks and isolated accounts. M02 gives P19/N20, accrual101, effective risk81 and available31. |
| Risk and cash | Effective risk subtracts H once; availability uses that result without another H deduction. The separate USD cash test also accounts for H but is an additional constraint, not another equity debit. |
| Credit | H enters each debt/LTV limit as an independent constraint; effective available supplies the separate IM bound. Taking the minimum does not add these constraints together. M14 gives quote80, post-proceeds risk8 and MM4. No borrowing permission follows from that quote. |
| Settlement | At unchanged unrelated state, cash minus D and own P minus D preserve effective risk. M04 retains principal20/interest2 and risk69/available56.8 after fee and payment. M05 ends cash-2, deficit2, P0, with no invented loan or second debit. |
| Receivers and accrual | Cash-minus-P-plus-N remains101 throughout M06, while spendable risk rises only when the20 receipt commits. Unapplied correction credits similarly grant no risk credit. |
| Uncertain rate | M10 fixed exposure produces ceiling U6, final toward-zero P2.46 and release3.54. U and P cannot coexist for the same duty; cap breach and missing exposure remain explicit restrictions. |
| Native cash and tiers | M11 outgoing38 reaches available0 with risk50>MM10;88 is only the native cash bound. M12 revalues the BTC tier inventory130→105 and retains the funding deduction once. |
| Rounding and ownership | M03 rounds each period .015→.01 rather than aggregating to.03. M17 pays receiver.01 with payer cash0/0, requiring real treasury-.01; aggregate customer plus treasury cash is zero and clearing returns to zero. |
| Existing orders and equality | M08 availability-10 remains until cancellation is confirmed; MM safety is a distinct condition. M09 equity5=MM5 triggers distress but cannot veto trusted mandatory cash. |
| Missing live risk data | M16 numeric exposure stays-17 after cash5→-7 and remaining P10. It establishes no successful current valuation. The proposed durable restriction/outbox is required and remains unimplemented. |

The continuity result relies on the retained reference domain: USD market price/collateral factor and all USD collateral tiers are one (`portfolio._inputs`). It is not a rule for discounted or depegged settlement assets.

## B1: define identity before a final cut exists

The specification and traceability define the economic key as `(authority_id, authority_generation, obligation_id, account_id, settlement_asset, final_cut_sha)`. An unknown-rate U is created from an immutable exposure cut before a final cut exists. Consequently this sole published key cannot yet identify U, and changing its last component later changes the identity that is supposed to prevent duplicate U/P contributions. M07 covers executor generation, but does not define this separate exposure-to-final transition.

Before implementing R001/R013/R014 and invariant I01, define a stable duty key independent of final-cut availability. Retain immutable exposure-cut and final-cut hashes as separately typed evidence references, together with an explicit one-active-representation state transition and version/uniqueness constraints. Resolution must atomically consume U, record exactly one P/N representation and its linked final cut, and advance the same economic duty; duplicate resolution, sign change, zero rate, crash and replay need exact expected states. A reserved placeholder hash without that transition contract is insufficient.

This is a missing design definition, not an observed duplicate in the existing runtime.

## B2: resolve mandatory payment against existing spot locks

R006/R009 require existing native spot locks to remain real until confirmed cancellation, and the specification retains the base `frozen <= gross` invariant. R010 requires trusted mandatory funding cash to settle despite insufficient spendable cash. The policy does not define how these coexist when payment crosses locked cash.

A permitted pre-payment component set is USD cash100, existing USD spot lock95 and P12. The base reference risk is5; effective risk is-7. Paying12 with unchanged spot lock leaves gross USD88 and frozen USD95, which violates the retained model invariant. `LoanAccount.__post_init__` explicitly rejects this state. The base supervisor calculates risk before its later local spot-cancellation step, so the existing code cannot be assumed to resolve it automatically. Missing-current-market degradation addresses a different cause.

Before enabling such a combined authority, choose and specify one boundary: either atomically perform a genuine confirmed local spot cancellation/preemption before payment, preserving already confirmed/in-flight settlement obligations and recalculating after the lock release; or reject the unsupported spot-lock capability and all ways to introduce those locks into this new authority. If external cancellation is supported later, its pending acknowledgement cannot be fabricated as a release. Add the crossing-lock example, partial-fill/cancel ordering, payment-before/after cancellation, restart and complete period atomicity to the rule and acceptance matrix. Do not silently weaken `frozen <= gross`, hide a lock, invent principal, or roll back a valid payable merely because its own hold consumes cash.

This blocks full combined settlement semantics until resolved; it is not a claim that the documentation executed a failed payment.

## Remaining release gates

The specification correctly keeps old-writer exclusion and all incremental-risk entry points open. A config string, a source pin or this arithmetic review proves none of those fences. New schema/capability mappings must reject legacy service/credit/spot/matching/constructor/takeover writers before financial or capability effects. Every admitted operation needs a complete historical P/U/N basis, serialized account/funding versions, original order/fee/partial-fill constraints and unchanged permissions. Unimplemented operations must reject explicitly.

Actual cut/hold atomicity, mandatory settlement without current quotes, durable restriction/recheck recovery, historical-watermark replay, unknown results, complete-period and per-currency conservation, independent old-binary denial, real matching, capacity and storage faults all remain unexecuted. Cross-account transfer/custody, corrections, insurance and ADL remain unsupported until separately accepted. The separate PR52 valuation10/order11 integration and any new credit/engine binding require their own exact contract review.

The local system policy attribution is appropriate: no exchange behavior is claimed from these examples. A subsequent specification correction must receive a new immutable pin and an explicit review of its changes. There is no financial, deployment, production or real-funds signoff in this report. Reverting the report/evidence changes no runtime or data; any eventual financial rollback must preserve obligations, holds, receipts and confirmed ledger effects as the design requires.
