# Independent finite Cross valuation and borrow enumeration

CODE_ONLY / NOT_RUN. This test-only candidate starts from public PR51 source
667171d1f248f571b3f3386402bdc02f1fc0dc92. It changes no UTA source,
service selection, account authority, database schema or trading route.

The independent oracle uses Fraction for direct two-asset valuation and checks
every representable positive borrow quantity in its finite domain. It imports
model definitions and calls the decimal candidate under test. It does not call
calculate_cross_risk, CollateralRule.discounted, production floor/ceil helpers,
service risk, or any production borrow calculation.

Inputs have USD and BTC gross balances, separate same-currency principal and
interest, frozen balances, USD cash deficit, signed linear quantity and signed
cost including one subunit of dust, order reserve, varying asset and mark prices.
BTC collateral uses marginal 80% through USD100 and 50% above; its LTV is 50%.
USD collateral LTV is 80%. The base USD and BTC maximum principals are20 and1,
steps1 and0.1, debt capUSD50. The maximum positive candidates are20 and10 units.
Proceeds leave collateral immediately. Feasibility checks principal, total debt,
loan collateral, available IM and strict post-borrow MM separately.

Five fixed methods propose536 completed vectors:512 integer-generator cases
with seed20261118,6 tier/freeze boundaries,8 maintenance/reserve boundaries,
8 hostile Decimal-context cases, and2 independent zero-rate strict-borrow cases.
The latter separately use USD LTV1, IM/MM0: USD10 supports at most9 whole USD
borrowed; USD10.01 supports10. Equity equal to MM after borrowing is rejected.

For a default flat account holding USD100 and BTC2 at100, BTC discount is130,
risk equity230, loan value145; max borrow is USD20 and BTC0.5. These manual
values precede execution. Every success retains exact finite input, feasible
unit list, expected rational values and actual candidate values on its test
instance for a future bounded entry to archive.

This is a finite synthetic specialization, not full model coverage. No claim
covers options, inverse contracts, Isolated/PM, large precision/exponent bounds,
service activation, concurrency, SQL, matching, throughput or production.
An independent reviewer must check the oracle and fixed cases before a single
bounded first run. Preserve FAIL/UNKNOWN, inputs and outputs without retry.

Deployment introduces tests only. Rollback removes this test module and its
contract while retaining PR51 runtime and all historical evidence. No data
migration or product activation is involved.
