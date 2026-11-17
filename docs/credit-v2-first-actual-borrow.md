# First actual internal synthetic native borrowing checkpoint

The first actual positive BORROW checkpoint passed on source commit
`3e3e8133d9fc8e734a6fb244bf989d7010aed23e`, Python3.12/CPU3, at
2026-11-17 14:46:31.429596–14:46:38.264695 UTC (6.835s process time;
one unittest 6.699s). This is a small correctness run, not a throughput result.
Exact commands, all source/test hashes, raw output and complete retained SQL
observation are in `evidence/runs/credit-v2-first-actual-borrow/attempt-01`.

The test used real public constructors for a new synthetic audited USD8/BTC8
Cross account, funded pool, explicit limits and golden product/risk policy.
The real fresh-only installer published the complete immutable V2 capability;
actual internal lease acquisition returned a real fencing token. New services
were constructed from the actual token-bound Database using the verified
read-only factory, with no rebinding of old bootstrap services.

The explicit synthetic producer committed original source+PENDING, then the
actual FIFO executed a 0.4 BTC loan. The native intent, four ordered journal
legs, customer balance, gross principal, account version, complete dedicated
credit decision, original receipt/event and SUCCEEDED terminal closed under
the original financial COMMIT. The actual journal was sealed and the actual
foreign-key check was clean. Dedicated operation replay matched the actual
retained bundle. Reopening services verified the complete journal; original
CID query/retry returned the same terminal receipt, with exactly one source,
intent and decision. A further worker poll had no operation to execute.

The actual bound service still returned `ready:false`; public new borrowing
still failed with `unsupported_credit_operation`501 and no extra effect.
The original bootstrap object remained unbound. This authority supports only
the restricted internal synthetic scope described in
`credit-v2-financial-hooks.md`; it is not a generic trading worker or a real
customer account migration target.

The original private temporary database is retained outside Git for the
independent oracle to read actual SQL. Public observation contains only selected
synthetic credit/accounting records, not writer lease/auth rows or the actual
owner nonce. Its bundle is content addressed local evidence, not a signed
COMMIT certificate. Physical COMMIT timestamp remains explicitly null. This
author-run checkpoint does not sign its own independent financial acceptance.

Next gates are independent original-DB reconciliation, partial/interest-first
repayment, historical replay after later effects, actual process restart and
lost-response recovery, full actual late-catch/SAVEPOINT/unknown/corruption
negative matrix, complete installed-V2 old-binary refusal and supported Python
versions. HMAC origin, trading/matching/lending-distress adapters, interest and
pool changes after publication, insurance/ADL, real currencies, performance/HA
and real-funds approval remain blocked. No HTTP/CLI activation was added.

There is no production deployment step at this checkpoint. Before any V2 marker
exists, ordinary binary rollback is possible. After publication use the exact
retained compatible runtime, query original CIDs and recover forward; do not
delete the marker, downgrade the format, reassign a static claim or erase a
confirmed loan. The retained test database will be removed after independent
read-only evidence capture.
