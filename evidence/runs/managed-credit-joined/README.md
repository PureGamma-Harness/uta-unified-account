# Joined borrow targeted verification

This evidence belongs to the connection-joined borrowing refactor, based on
`07d0a72` plus its plan commit. Exact tested runtime/test hashes are in
`manifest.json`; this is not a clean frozen full-release report.

Each runtime executed the same **70 tests**, with zero failures/errors/skips:
CPython 3.12 in 3.708s, CPython 3.10 in 3.941s, and system CPython 3.13 in 4.075s.
The 3.13 invocation promotes ResourceWarning; no warning was observed in these
raw logs. Tests cover existing credit, joined repayments, gross liabilities,
Cross rules, shared credit supervision, writer fencing and ten new joined-loan
cases. No benchmark or long run was executed.

The new cases use actual SQLite transactions and independently specified cash,
principal, pool, journal count and risk values. A real SQL failure after the
loan and a staged receipt rolls all effects back. Two loans share pool cash
and the database asset limit; a later order reads staged gross debt rather than
the original account margin. Private borrowing rejects unowned raw connections,
wrong authorities and read/inbox/control roles without elevating them.

`initial-fixture-error.txt` is an unchanged rerun of the initial fixture error:
the test selected nonexistent `producer_transaction` rather than the actual
`inbox_transaction`. Its nine other cases passed; the corrected fixture then
passed all ten. This test setup error is not a financial runtime failure.

An AST comparison verifies that the former public borrow's complete transaction
body remains unchanged inside the new helper, after strict join and input
preparation. The old general ledger join semantics remain unchanged; the new
strict financial join check is opt-in. Managed online borrowing remains
unsupported, and this refactor does not supply missing credit decision audit.
`production_approved=false`.
