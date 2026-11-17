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

## Minimum correction and actual retest

Commit `704a7a32106f3c5cd522dbc6bb35437f3634c01a` changes only a
non-current CID candidate to return zero before validating current operation
rows. The current CID's digest, trusted expected rows, actual staged-intent SQL
predicate, closing validation, and final denying trigger remain enforced.

CPU4 retest ran on new disposable databases at 14:56:16.975427–14:56:35.558977
UTC, process 18.586 seconds, three unittest cases passed. The original observer
now shows historical candidate zero returns without a guard exception. Actual
repayment commits principal `0.3`, two intents, four journals, both original
commands `SUCCEEDED`, and no foreign-key errors. Another real chain commits
two Alice loans and a Bob loan with three dedicated decisions and full ledger
verification. Bob was created and funded through actual public bootstrap before
fencing; the fixture extension changes no existing fixture default.

Five actual negative subcases attempt financial transactions and catch their
inner error: no operation scope, actual SAVEPOINT rollback removing the intent,
wrong current account version, a direct current-CID/wrong-digest gate call, and
immediate DROP TRIGGER. Each outer transaction still raises at physical COMMIT,
the full selected financial tables equal the pre-attempt snapshot, and the
original source command remains `PENDING`. The direct wrong-digest call is a
negative scalar gate test; it is not represented as a successful financial row
mutation or a granted permission. No simulated successful UDF/context is used.

Retest raw is in `attempt-02/`; the original `attempt-01/` exit-1 evidence is
unchanged. These checks establish this specific runtime correction and its
negative boundaries. Broader fault/restart coverage and independent financial
acceptance remain separate gates; production and real funds remain disabled.
