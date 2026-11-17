# Independent repayment reference: preregistration

Initial status: PENDING. No real SQL has been opened for this new phase. The
independent reference `2b83a47`/`205abbc95` predates the repayment implementation
and all actual observations. This adapter imports only that owned integer/
Fraction math and the independent data mapper, never a `uta` core function.
The original author native-repayment REDs and repair remain unchanged; a new
component PASS cannot relabel them. Author follow-up result is `5d8839d`.

## Hand-checkable cases locked before executing the new checker

Units are BTC 10^8; balances retain USD100 and all gross components. R1 starts
with cash/principal .4, interest0, pool .6. Repay .1 produces cash/principal .3,
pool .7 and principal receivable .3; interest cash stays0. The four ordinal
legs are customer−.1, principal liability+.1, pool+.1, principal receivable−.1.

R2 starts with cash/principal .4, opening interest .05, pool .6, interest
receivable .05. Repay .1 first pays interest .05, then principal .05: cash .3,
principal .35, interest0, pool .65, principal receivable .35, interest
receivable0 and interest cash+.05. Seven ordinal legs are customer−.1,
interest liability+.05, principal liability+.05, interest cash+.05, interest
receivable−.05, pool+.05 and principal receivable−.05. Opening interest consumes
debt, but payment of it never becomes principal returned to the pool.

Unlike the older manual M5's cash .5 input, actual R2 starts with cash .4.
The expected .3 output here is derived from that explicit input; the original
manual M5 input/result is never overwritten. Repayment must work while halted
and with stale/missing quotes. It requires sufficient unfrozen BTC cash and
existing debt, not a fresh borrowing quote, IM admission, account borrowing
limit or static unused loan budget.

## Data and proof boundaries

The new retained REPAY observation has source/inbox/intent/declared legs,
original receipt/journal, five original financial tables and actual post
interest cash. No borrowed decision is synthesized. Market dependency is NONE;
SID, risk, quote, quantity step, borrowing limits, selected checkpoint,
operation ID and decision kind are null where defined by this contract.
The adapter verifies those facts, original CID/account/source/hash relations,
receipt and terminal identity, version advance, full original chain and all
materialized balances. The independent math derives paid interest/principal,
post cash/debt/pool/receivables/interest cash and four/seven actual legs. The
producer's expected-posting table is compared against those independently
derived legs, never used to generate them.

All events are revalued as integer postings per currency with sequence,
ordinal, sealed and original event hashes; prehead balances supply the actual
opening interest-cash balance. This is data replay without a new SQL connection.
File content cannot prove native execution, FIFO timing, source COMMIT,
financial COMMIT atomicity, crash/restart or the authenticity of raw SQL rows.
Those claims remain separately pending until an independent read-only original
database observation and execution/fault evidence are supplied. Current final
inbox order alone cannot prove which head was eligible at the original time.

Actual fixtures use an injected fixed synthetic UTC clock, not a live wall
clock test. The separate real-UTC/SID case is outside this repayment financial
review. No production, performance, HA or real-funds approval follows.

Planned file-only command:

```sh
python scripts/credit_v2_repayment_reference.py actual-repayment-financial-observations.json
```

Original SQL scope, when separately scheduled: CPU4, at most15 seconds total,
only the two retained fresh0700 repayment DBs under the author-owned root.
Use mode=ro/query_only/SELECT authorizer and one snapshot each. Select original
source/inbox/intent/receipt/journal/financial rows directly; compare actual
receipts/ledger/interest cash and final current FIFO, and prove no new borrowing
decision row for the repayment CID. Never read owner/fence/auth/nonce tables or
the old borrow/soak DBs. No writes, service, native restart, signals or retries.

This is an offline checker-only change, with no deployment or data migration.
Rollback reverts new checker/reference files in a fresh commit while retaining
all original red/green evidence and private originals. It does not modify
authority, money, immutable journals or enable a public borrowing route.
