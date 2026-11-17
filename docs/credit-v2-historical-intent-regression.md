# Historical intent candidate evaluation: actual red

The real disposable synthetic FIFO reproduced the partial repayment failure at
source `9f47d032f5d4718a4900686d77ff1c986e7f40a2`. CPU4 ran from
2026-11-17 14:54:24.776635 UTC to 14:54:30.728767 UTC (5.955 seconds).
The raw unittest exit is **1**; it has not been recategorized as a passing test.

The observer used Python execution tracing of the unchanged actual `_sql_gate`
function. It neither replaced the gate nor changed any return value. SQLite
evaluated the `POSTING` gate first with historical `loan-first` intent identity
while inserting the new repayment's customer posting. That candidate mismatch
poisoned the real transaction. The next matching `repay-second` candidate then
failed because the transaction had already been poisoned. This confirms a real
runtime bug caused by relying on SQL predicate evaluation order, not a mismatch
between the repayment's four-leg arithmetic and the ledger's canonical order.

After physical rollback and a new actual read transaction, the original loan
was `SUCCEEDED`, repayment remained `PENDING`, principal remained `0.4`, the
original one intent and three journals remained, and `foreign_key_check` was
empty. No retained or live database was opened. The fixture cleaned its own
temporary directory. Public raw includes selected loan identity and financial
rows only; it does not include a writer nonce, token, or authentication secret.

The correction must make a historical nonmatching intent candidate return zero
without granting permission or poisoning the actual current operation. A
protected SQL mutation with no matching actual staged obligation must still
invoke the final denying trigger and poison COMMIT. A current intent with wrong
digest, amount, leg, or identity must still fail. This report does not approve
the V2 capability for production or real funds.

Raw: `evidence/runs/credit-v2-historical-intent/attempt-01/`.
