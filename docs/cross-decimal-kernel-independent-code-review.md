# Independent Cross decimal-kernel CODE review

**CODE_CLOSED_FOR_FIXED_PURE_ENTRY_PREPARATION**, not execution approval.
Reviewed financial/test source `a819182c35b79561277321bcef24ed706346b4ea`
and author delivery `2cfec40e6ae1794782d9b56fea158b2442d74acf`, based on
PR49 `7665253ced0888e8204b9806b63c4163f2cafe42`. No concrete numerical
blocker was found in the stated exact-class, validated immutable-model domain.

All66 inputs/1348810 bytes match their canonical regular physical files,
lengths, SHA-256 and both frozen Git trees. Manifest37fb201e and planbbe15159
match their exact digests. The original61 UTA modules, service/default,
validators and loaded-module set are unchanged. Only the new pure module is
added to UTA. The artifact test explicitly advances its path inventory toV2,
with62 exact keys; it does not rewrite historical61-source plans. The other
five tag-test method ASTs remain unchanged.

## Arithmetic and policy equivalence within the stated domain

Coefficient/exponent addition aligns powers of ten; multiplication adds
exponents. Signed coefficient determines comparison without context-sensitive
Decimal operations. Fraction conversion, GCD, the reference calculator and
reference collateral arithmetic are absent from the candidate valuation path.
Shared model types, market freshness validation and catalog capability checks
remain policy dependencies, not independently verified market authenticity.

The field-by-field comparison preserves gross accounting assets, discounted
free collateral, gross principal/interest/cash-deficit values, frozen value,
loan value, signed linear multiplier valuation and cost, separate IM/MM,
order margin, available margin and status. Same-coin assets/debt are not netted
before haircut or liability valuation. Cash deficits add full debt without
fabricating principal IM/MM. A surviving signed cost may be negative or cross
zero. There is no new currency-unit rounding. Metadata and the existing
CrossRisk constructor field order agree with the reference.

For positive step s, floor(min(caps)/s) equals min(floor(cap/s)); clamping
negative minima at zero is preserved. Strict maintenance imposes an integer
upper bound n < (equity-MM)/(price*s*(1+MM_rate)), whose largest allowed
integer is ceil(the quotient)-1. The implementation uses signed integer floor
division and negation to obtain that ceiling, including exact equality and
nonpositive headroom. Borrow quotes remain independent single-asset quotes,
not a jointly spendable sum.

The reviewer separately used stdlib rational arithmetic and literal policy
inputs, without importing either calculator, to check M01: collateral1105,
debt112, PnL40, risk equity1033, loan value852.5, IM56.3, MM28.15,
availability966.7 and individual USD/BTC borrow quotes388/3.88. M02's gross
200 collateral haircut to160 before130 debt yields equity30, IM13 and
MM6.5. Tier/subcurrency, deficit, long/short and cost-dust literals were also
checked algebraically against the declared formulas. An exact strict-MM
example admits9 rather than10 units; the nonterminating cap40/11 floors to3.6
at step.1. These are independent review calculations, not observed target
results or exchange-policy certification.

Decimal output construction agrees with the reference's exact representation:
positive exponents expand to exponent0, fractional trailing zeros are removed,
and zero is positive with exponent0. Exact numeric-equal cache keys therefore
preserve canonical output. Validation occurs before scalar memo lookup;
positive/nonnegative/rate constraints still run on reused scalar values.
Nonfinite scalars reject before hashing. Exact model/Decimal subclasses are
an explicit unsupported specialization; no silent fallback is installed.

The input digit/exponent limits duplicate the reference's80-digit,
absolute-exponent100 and nonzero-adjusted-exponent100 checks. Finite chains
use at most four input factors. A conservative alignment/ratio exponent
difference bound is700, below the implementation's1000 power ceiling;
output conversion also stays within that bound. Arbitrary Python integers
avoid machine overflow. Call-local scalar memoization stops adding at2048
entries; powers have at most1001 entries. This is a static domain derivation,
not a measured memory or CPU bound, hostile-object sandbox or formal proof.

## Test and activation gates

The nine direct test selectors are defined with their required globals/imports.
The finite grid contains96 combinations. Twelve pre-implementation manual
case IDs include full-field and boundary expectations. Differential calls use
the unchanged reference as an oracle; the new hot path does not call it.
The low Decimal-context/trap cases, exact tuple comparisons and immutability
checks are coherent statically, but have not been executed in this review.

A whole-module bounded entry and caller are not prepared. Target import,
bytecode compilation, tests, SQL, workers, monitoring, process probes and
benchmarks remain0. AST parsing and review-owned stdlib arithmetic alone ran.
The nine tests, first RAW, wider properties and real Cross performance remain
OPEN. H73 measured legacy_reference, not this Cross calculator, and supplies
no speedup evidence for it.

No service adapter activates the new callable. At-rest source coverage does
not establish its future loaded-engine/policy binding. Any opt-in needs a
separate review of that binding, source inventory, authority compatibility and
rollback, followed by actual differential and integration results. Default
reference, Isolated/PM and later products are unchanged. Production, real
funds, capacity, HA and human financial approval remain unapproved.
