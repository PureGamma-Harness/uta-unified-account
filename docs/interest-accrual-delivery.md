# Interest arithmetic delivery boundary

This branch adds the pure spot-loan accrual kernel and independently frozen
Fraction standards above recovery delivery6010e92. Its core bytes still equal
the tested componentc507e0b; existing credit service, V2 certificate and financial
dispatch paths do not change. The integration scope is recorded in
`docs/reviews/interest-accrual-delivery/root-source-scope.json`.

The author recorded16 focused passes. The independent group first froze12
manual cases and a separate Fraction calculator, then recorded68 candidate
checks:12 manual,32 partition invariants and24 lifecycle boundaries. Its20
reference selfchecks are separate. Exact equality with a rate's valid-to endpoint
was statically reviewed but not independently exercised as a positive case.
These are deterministic arithmetic results, not throughput, persistence or
financial-authorization evidence. Integrated CI must test the combined tree.

Deployment remains an unactivated library experiment. V2 still requires zero
new interest; no scheduler, loan-source permission or ledger posting is added.
Before any later integration, atomically persist the unique reference, interval,
cursor, fractional carry, actual unpaid liability projection and same-currency
journal legs under the authoritative writer. Preserve a single stream per
account/asset across zero principal and new borrowing; a new stream ID must not
erase carry or create extra charges. Unsupported closing/waiver/migration remains
an explicit gate.

Rollback removes experimental callers and retains their original references,
state/carry snapshots and audit history. It must not recalculate or reverse
actual financial entries from this pure model. Product, deployment, model and
real-funds acceptance remain open; the full rules and refusal behavior are in
`docs/interest-accrual-kernel.md`.
