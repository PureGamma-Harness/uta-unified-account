# Existing-only constructor snapshot join

`writer_fence._assert_existing_read_joinable(database, connection)` lets a real
existing-only constructor join the exact original read/control transaction. It
checks registry identity, connection and Database object identity, active SQL
transaction, original owning thread and the actual role. Financial, inbox, raw
and merely same-path connections are refused. A previously poisoned guard stays
refused. When a writer token is bound, the original actual fence checks validate
that token in the same snapshot.

This helper opens no transaction, grants no role, transfers no actor and skips
no ledger/credit/schema/config verification. Read-snapshot token checking is not
a claim that a future writer still owns its generation; every later financial
transaction continues its actual lease/fencing checks. The caller must perform
the original complete existing-state verification. No `_OwnedStartup`, `__new__`
fixture or successful verification flag is manufactured.

Four actual private-tempDB microtests passed on CPU4/Python3.12 in0.032s,
13:53:36.346081–13:53:36.486139 UTC, ResourceWarning errors enabled. Real
read/control joins work; the control join still cannot update a financial table.
Financial/inbox/raw/other-Database/foreign-thread joins fail. A true acquired
base-format token is accepted before its synthetic local fence expiry and
refused at expiry. No native V2 owner, loan, publisher or listener is created.
Exact source hashes, command and original raw output are in
`evidence/runs/existing-read-joinable/`.

```sh
python3 -W error::ResourceWarning -m unittest tests.test_existing_read_joinable -v
```

This isolated join helper has no schema/data migration or activation. Its code
can be reverted before dependent read-only factories ship; it is not an
acceptance of those separate factories or of native V2 recovery.
