# Independent review: finite Cross enumeration oracle

**CODE CLOSED for the fixed two-asset synthetic specialization at
`7b449f30b417e043bf13a4f43540102b13c4d588`.** This is an independent static
financial-oracle review, not an executed differential result, full Cross
validation, service activation or production acceptance. Target import, compile,
test, SQL, native/process/PID, CI and child-agent attempts are zero.

Reviewed tree `1b664154bdb65b1cd1b76b6da25e0bc8709b8977`, sole parent public PR51
`667171d1f248f571b3f3386402bdc02f1fc0dc92`. All64 canonical regular physical
inputs match plan lengths/SHA256 and Git objects:1,327,705 bytes. All62 UTA Python
files are byte-identical to parent. Plan is11,043 bytes, SHA256
`d95a7acbb2de9e7d3daab581cec076354315585fb2021521c97cfcc4a0778f87`.
The source worktree was clean. Git/text/byte hashing/stdlib AST only were used;
the generator, oracle, candidate and target models were not executed.

## Independent valuation and maximum proof

The oracle's direct calls are only Fraction, abs, dict, map, max, min and range;
its attribute calls are append/get. It imports shared validated model types and
calls the decimal candidate under test, but it does not call the reference
calculator, production discount, floor/ceil, borrow or service-risk functions.
It hardcodes the explicitly fixed fixture rules rather than obtaining expected
answers from candidate helpers. Future rule changes require a new oracle review.

Gross assets remain gross: frozen units reduce eligible collateral and LTV,
not accounting assets. USD/BTC principal and interest are valued separately;
USD cash deficit is an additional debt component. Holding gross assets and debt
of the same currency does not authorize netting before collateral discount.
Free BTC notional up to100 receives80%, the excess50%; its resulting collateral
receives50% LTV, while free USD receives80% LTV. Spot IM/MM charge principal plus
interest, and linear IM/MM use absolute marked exposure. Signed marked quantity
minus signed whole-position cost gives PnL, including the signed cost dust.
Cash deficit reduces equity/debt headroom under the existing fixed model; this
test does not invent another principal or silently add a new deficit margin rate.

Each proposed loan leaves proceeds outside collateral, so value v increases
debt and reduces equity by v without increasing collateral or LTV. The independent
positive-quantity checks are therefore:

- current principal + quantity is at most the currency principal cap;
- total existing debt + v is at most50 and at most current lending value;
- current available margin - v - v*new-loan IM rate is nonnegative;
- current risk equity - v is strictly greater than current MM + v*new-loan MM rate.

These are post-loan constraints, not the candidate's minimum-of-divided-bounds
formula. The oracle tests every positive whole USD quantity1..20 and every BTC
quantity0.1..1.0, then takes the largest passing step. No omitted larger positive
step could satisfy principal cap20 USD/1 BTC because current principal is
nonnegative. Thus the maximum proof is complete in this finite domain, including
fractional remaining principal headroom, interest, debt-cap and IM constraints.
The initial list entry0 is a no-additional-loan sentinel; it is not proof that
an already liquidating account is safe or that a zero-quantity command is valid.

## Independent hand calculations

Default USD100/BTC2 at100 has accounting assets300. BTC collateral is
100*.8+100*.5=130, giving collateral/risk equity230 and lending100*.8+130*.5=145.
USD20 passes and its next step violates principal cap20. BTC0.5 consumes debt
cap50 exactly; BTC0.6 would consume60 and fail. These are separate single-currency
quotes: executing both would consume70>50, so the output vector is not a joint
loan authorization or proof of concurrent reservation safety.

For the zero-rate cases, USD LTV1, no debt/position/reserve and whole-unit step
give IM/MM0. USD10 can lend9: quantity10 leaves equity0 equal to MM0 and fails
the strict test. USD10.01 can lend10, leaving.01>0; quantity11 violates LTV/IM.
The special test independently enumerates these integers; it does not use the
default oracle with the modified rules.

As a review hand check only, take gross USD100/BTC2, frozen USD20/BTC1.5,
principal USD3/BTC.1, interest USD.5/BTC.005, USD deficit2, reserve1, BTC spot100,
and linear quantity-.1 with cost-10 at mark120. Accounting assets300; principal13,
interest1, debt16, PnL-2, accounting equity282, frozen value170. Collateral is
80+50*.8=120, lending64+20=84, risk equity102. IM is.35+2.1+1.2=3.65; MM is
.175+1.05+.6=1.825; available margin97.35. USD17 is principal-capped; BTC.3
passes but.4 makes total debt56>50. This calculation is additional review
reasoning, not an added executed vector or a change to the536-vector budget.

Status tests use risk equity<=MM for LIQUIDATION before available<0 for
MARGIN_CALL. With long1 at mark/cost100, MM5 and IM10, cash5 is liquidation
equality, cash5.01 is margin call, and cash11.01 is healthy at reserve0 but
margin call at reserve3. Every one of those eight fixed cases quotes zero
positive borrow; they test status/reserve boundaries, not positive IM step equality.

## Exact coverage limits and next-entry gates

AST and source confirm five fixed methods and planned counts512+6+8+8+2=536.
These are completed checks if successful, not536 proven distinct economic states.
The hostile-context method intentionally repeats the first eight generated inputs
under precision2/Inexact/Rounded traps. Exact Decimal tuple construction and
Fraction valuation avoid ambient Decimal arithmetic in expected/input calculations.
The planned tier cases cover immediately below/at/above100 and full BTC freeze.
No target assertion has run, and the default manual case is documented, not a
separately registered536th-or-extra test vector.

Concrete open extension CROSS-ENUM-COV-001: fixed positive borrowing rates have
IM>MM. If a positive quote passes IM, then post-borrow equity>=old IM+reserve+
v*IM rate, which is strictly above old MM+v*MM rate. Consequently none of the
default-policy cases can activate a nonzero-rate strict-MM cap; the two modified
cases exercise rate0 only. A future equal-nonzero-rate example would be USD11,
LTV1, IM=MM=.1, step1: quantity10 leaves equity1 equal to MM1 and must be rejected,
so maximum9; USD11.01 permits10. This is a specific uncovered policy extension,
not an error in the declared fixed-policy oracle and not an added run request.

Coverage also excludes BTC cash deficits, additional currencies/products, variable
rules/multipliers, missing/invalid/stale inputs, extreme precision/exponents,
joint loan vectors, SQL, admission/concurrent reservations, matching and PM/
Isolated/inverse/options. Existing tests elsewhere are not borrowed as evidence.

The retained entry is still OPEN. `completed_vectors` appends after successful
comparisons, so a failed check is absent from that list. A future entry must
retain first failed inputs/expected/actual before assertions or via another
independently reviewed failure capture; successful-vector counts alone cannot
prove complete failure evidence. Freeze exact source/runtime/selectors/resources,
bounded output and actual exit/reap/EOF capture before a separate root GO.
Preserve the first FAIL/UNKNOWN without retry; independent RAW review follows.

No deployment or data migration occurred. Rollback removes only these tests/docs
and their preparation while retaining parent runtime and historical results.
Reference math and default service selection remain unchanged. Production,
capacity, real-funds, insurance and ADL activation remain NO_GO. This review's
index mutations were confined to its new independent review worktree; no main
worktree/index operation was performed.
