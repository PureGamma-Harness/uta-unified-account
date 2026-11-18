# Cross decimal-coefficient candidate: specification before implementation

Status: CODE preparation only. No target import, compilation, test, SQL or
benchmark has run. The baseline is PR49 `7665253ced0888e8204b9806b63c4163f2cafe42`.
This candidate will be a separate pure function; no service call site, default,
API, persisted policy or product capability changes.

## Numeric contract

The reference is `calculate_cross_risk` in `uta/portfolio.py`, rule
`UTA-CROSS-LOAN-v1`. Its amounts are exact terminating values: assets and debt
remain gross separate components; frozen assets reduce collateral but remain
in accounting assets; collateral tiers are marginal USD bands; cash deficits
are full-value debt without borrowed-principal IM/MM. Linear signed cost may
cross zero because settlement dust is valid. Rates come from `PortfolioRules`,
not the market instrument's reference margin rates.

Represent each finite value as `(integer coefficient, decimal exponent)`.
Addition aligns powers of ten; multiplication adds exponents. There is no GCD,
Fraction construction, float conversion or ambient Decimal arithmetic in the
candidate valuation path. Construct output Decimal values directly from their
tuples. Normalize fractional trailing zeros and expand positive exponents so
the reference's exact Decimal representation is retained, including zero.

There is **no intermediate USD/currency quantization** in this calculator.
Settlement-unit floors/ceilings belong to the service and are not introduced
here. Borrowable quantity alone is rounded down to `quantity_step`. For a
positive step `s`, compute integer units directly as the minimum of the floors
of the four caps divided by `s`, clamped at zero. For strict maintenance, impose
`units < (risk_equity-MM)/(s*price*(1+borrow_MM_rate))`; its greatest integer is
`ceil(the quotient)-1`. This avoids constructing nonterminating quotients.

Return the existing `CrossRisk` type and every existing field, metadata, status
and per-asset borrow quote. Its type has no margin-ratio field. The service's
34-significant-digit half-even ratio formatter is outside this candidate and
is unchanged; no ratio field is invented.

## Supported domain and bounds

Use the existing validated immutable model classes, USD settlement/reporting,
Cross only, collateral/borrowing and supported linear perpetual exposures.
Pure valuation retains the reference's multiplier metadata support; this does
not expand the service's actual multiplier-one execution capability.
Use `market.validate` for unchanged age/clock policy and the catalog's public
`require_risk_supported` for unchanged product capability checks. These shared
non-arithmetic gates are not an independent validation of feed authenticity or
product policy. Do not call the reference calculator, its collateral arithmetic
or its Fraction conversion helpers from the new calculation.

The candidate explicitly requires exact model/Decimal classes; subclasses are
an unsupported specialization, not reclassified invalid reference input. A
separate `DecimalKernelUnsupported` exception allows an explicit caller choice
to use the reference **before any financial effect**. No automatic fallback is
added. Model-accepted numerical inputs retain the existing bound: at most80
coefficient digits, absolute exponent100 and nonzero adjusted exponent100.
Maps retain the model's4096-entry and tier64 bounds. Inputs can be as small as
1e-100; arbitrary Python integers avoid machine overflow. Finite valuation
chains contain at most four input factors. Power alignment is bounded by1000
(conservative over the required exponent differences); local scalar memoization
has at most2048 entries and the local power cache at most1001 entries.

Malformed/nonfinite Decimal values and bool financial values reject. A source
snapshot modified after validation is outside the immutable-model assumption;
the candidate is not an adversarial object or process sandbox. Isolated, PM,
inverse, dated, options, hedge offsets and non-USD settlement remain unsupported.
Unsupported and numerical failures never become a successful zero-risk result.

## Manual cases, established before code

The accompanying JSON records literal human arithmetic, not values generated
by either calculator. Full-field cases M01/M02 and focused boundaries cover:
multi-asset gross same-coin debt, marginal tier/frozen values, separate interest
and cash deficit, multiplier long/short, legitimate negative cost dust, strict
MM/zero MM/negative equity, nonterminating borrow caps and step rounding.
Example M01: collateral1105, principal110, interest2, debt112, PnL40,
accounting equity1128, risk equity1033, loan value852.5, IM56.3, MM28.15,
order reserve10, available966.7; separate USD/BTC quotes388/3.88 are not additive.

The fixed CODE test plan will compare all fields with the unchanged Fraction
reference and separately assert the literal manual expectations. Low Decimal
contexts/traps, equal numeric representations, large bounded inputs, input
immutability and scalar-domain rejection are included. Differential agreement
does not by itself independently validate the reference policy.

## Delivery and rollback

CODE review, an explicit bounded pure-run approval, independent first-RAW
review and later performance measurement are separate gates. All actual
execution and speedup fields remain NOT_OBSERVED. Do not attribute the earlier
reserve-cache profile gain to this unexecuted kernel. No SQL, worker, market
publication, source-artifact exclusion or signature mechanism is changed.

Only future fresh synthetic authorities may opt in after validation. Existing
source-bound authorities require a separate compatible writer handoff; no live
hot swap or migration is supplied. Rollback keeps the unchanged reference as
the default and preserves all confirmed financial history. Production,
capacity, HA, product activation and financial human approval remain NO_GO.

## Source inventory and activation limitation

Adding the candidate module changes the package source set from61 to62. This
branch explicitly advances the ordinary artifact test's inventory toV2 and
requires the exact62 keys for both normal and injected retained-source checks.
It does not edit historical61-file plans or weaken their validators. Those
plans remain valid only at their original source; they are not executable
approval for this candidate. The original61 UTA files and credit loaded-module
set remain byte-identical. In particular, no credit/authority adapter calls this
new module: future activation must separately review the loaded-engine binding,
policy/code artifact and source inventory for the new callable. At-rest source
coverage alone is not a claim that this optional callable has live authority.

Two edit attempts combined an unrelated documentation context with a test edit;
apply_patch rejected the missing documentation context before either edit was
written. These are preparation-only errors, not target executions or test
failures. The subsequent isolated patch and static source checks bind the actual
files; no historical source or result was rewritten.
