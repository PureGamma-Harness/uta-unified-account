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


## Actual file and original-SQL results

The adapter/rules were owned at `3d3f95a` before its first file execution;
the original SQL checker was owned at `17889f24328a0729e06ad00c67c5d1e736e7cecc`
before any independent repayment SQL. The first file-only batch at
2026-11-17T15:07:17.541882–17.593144 UTC passed both observations in wall0.051283s.
The original26445-byte selected synthetic export digest is
`dfdcbc059363f6f28cd1537fe8756f5863fdb11d8362f8fd6503fe1637ae3c54`.
It is retained byte for byte; it contains no private database or auth/owner rows.

After root scheduled CPU4 and the native group explicitly released it, a new
immutable detached checker worktree fixed exact17889. The single original-SQL
wrapper ran 15:11:22.428698–22.573644 UTC, whole0.155034s including both children;
each child used <=5s timeout inside the <=15s whole budget. Both first attempts
passed, no timeout, retries, native executions or original writes. The original
DB identity remained device27/inodes578951 and578953, logical_changes0, checker
source clean and unchanged. The private originals stay private and unmodified.

Independent SELECTs of original source/inbox/intent/receipt/journal and all five
financial tables match the archived export. Full original chains of4/5 events,
actual ordinal legs, every event's per-currency balance, materialized balances,
original prehead and post gross debt/pool/interest cash match the independent
reference. R1's actual four legs leave cashBTC.3, principal.3, pool.7 and
interestcash0. R2's actual seven legs leave cashBTC.3, principal.35, interest0,
pool.65 and interestcash.05. Interest receivable is reduced separately, while
only principal payment returns to the pool. No fresh quote or borrowing
admission input is used. SQL confirms zero CREDIT_BORROWED decisions for either
repayment CID and final account inbox entries are SUCCEEDED with no earlier
PENDING entry. This proves the current final records, not their historical
execution ordering or a prior independent source-COMMIT observation.

**Scoped financial/content/original-SQL PASS** for these two cases. The content
subreport's provenance label intentionally remains pending because an input
file alone cannot prove SQL origin; this surrounding independently executed
read-only observation closes that part only. Native owner enforcement, FIFO
at execution time, source and financial COMMIT boundaries, unknown responses,
restart/crash and replication retain separate execution/fault gates. No live
wall-clock TTL or production behavior is approved by the fixed synthetic clock.
All author original REDs remain unchanged. No initial independent actual red
or rerun occurred. Raw commands, source hashes, output and timings are retained
under `evidence/reviews/credit-repayment-independent/`.
