# First actual follow-up: retained blockers

The next three actual cases on source1156ba1 ran once on CPU3 at
2026-11-17 14:48:38.377743–14:48:54.033758 UTC (15.656s). One passed and two
failed. Original raw, exact code hashes and selected read-only post-failure
financial observations remain in `evidence/runs/credit-v2-actual-followup/attempt-01`.
No successful first BORROW evidence was rewritten or rerun to hide these failures.

The quota case passed: 0.51 BTC exceeded the explicit gross account/allocation
limit, actual SAVEPOINT rollback removed all financial effects/intent/decision,
and only the original source and REJECTED409 receipt remained. The next account
FIFO loan then succeeded. This is an actual business-refusal/rollback result.

The partial-repayment case reached the actual native financial path and failed
on `ledger_postings` INSERT with the native scope/obligation guard. The outer
transaction rolled back. The original loan remained committed, repayment stayed
PENDING, and no repayment journal/debt/intent/decision committed. This is a real
runtime blocker for partial REPAY, assigned to the native implementation group;
it is not a passing rejection or an accepted repayment. The exact actual native
counterexample must be fixed and targeted independently.

The halt/stale-market repayment case failed earlier in this test author's
observational SQLite audit hook: `sqlite3.connect/handle` is delivered before
Connection initialization finishes, so calling `set_trace_callback` there raised
`Base Connection.__init__ not called`. That case did not execute a repayment.
It is a harness defect, not evidence of a market dependency or native financial
bug. Its source/PENDING persisted and original opening principal/interest stayed
unchanged. A corrected observer must attach after actual connection initialization
without substituting a financial method, market, guard or successful callback.

The independent oracle has separately passed the untouched first BORROW-only
original database. This does not accept repayment. V2 stays default off,
synthetic-only, non-trading-ready, with no public activation. Runtime and harness
fixes and their new targeted evidence will be separate commits; the original
failed run and all unknown outcomes remain retained.
