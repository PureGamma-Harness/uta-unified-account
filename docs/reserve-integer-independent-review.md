# Independent mathematical review of the decimal-integer reserve candidate

**PASS for the exercised plain-input mathematical and wire scope; production
and persistent-capacity gates remain false.** This review binds source
`057fa65d1d79ae1855e551e73b6f58eeb375197b` and core
`02c2193599f403dfe489b95e21123fcd1686ffc2`. It changes no author code, service,
ledger, schema, account state or runtime configuration. Three imported files
are individually bound in [source-pin.json](../evidence/reviews/reserve-integer-independent/source-pin.json).
The unchanged reference and experimental module are pure arithmetic; no other
tracked `uta/` text reference to the experimental function was found. This is
not a service-dispatch, durability, concurrency or 10,000/s acceptance result.

## Independent specification frozen before execution

Commit `d5a2ac9d1fc24b386c707d6e33b8c3ddc45969d1` froze a separate
[Fraction oracle](../evidence/reviews/reserve-integer-independent/frozen_fraction_oracle.py)
and [16 manually entered cases](../evidence/reviews/reserve-integer-independent/frozen-manual-cases.json).
It imports no production function. Its ceiling uses quotient/remainder, and
its exact decimal description uses a private large Decimal context rather
than either production conversion routine.

For signed remaining quantity `r=q-filled`, limit `L`, mark `M`, margin rate
`a`, fee rate `t`, prior fee notional `N`, charged fee `C`, and settlement
scale `s`, the independently specified terms are:

- Adverse loss: `max(0, r*(L-M))`.
- Initial margin: zero for reduce-only; otherwise `abs(r)*max(L,M)*a`.
- Cumulative target fee: `ceil((N+abs(r)*L)*t*10^s)/10^s`.
- Unpaid fee: cumulative target minus `C`.
- Reserve: the sum of margin, adverse loss and unpaid fee, without another
  aggregate ceiling or a clamp of negative compatibility values.

The signed quantity in adverse loss must not be replaced by absolute quantity.
For negative fee numerators, ceiling still rounds toward positive infinity.
The previous cumulative notional belongs inside the single ceiling; prior
charged fees are subtracted afterward. One hand case has a total target of
one cent already paid, so the residual reserve fee is zero rather than a
second independently rounded cent. Reduce-only removes IM, retaining adverse
loss and unpaid fees. Negative prices, rates, overfilled quantities and
overcharged fees are compatibility cases for this standalone expression,
not permission to admit those economic inputs as orders.

## Static arithmetic checks

Each decimal is an integer coefficient divided by a power of ten after
positive exponents have been folded into its coefficient. Alignment multiplies
only by nonnegative integer powers. Quantity/price scales are at most 18;
notional scale is at most 36; margin and final scales are at most 54. The
common final scale therefore preserves all three rational terms exactly.
`-(-n//d)` with positive `d` implements the same mathematical ceiling as the
independent quotient/remainder oracle for either sign of `n`.

Python integers do not overflow. The fast-domain limits also keep these
intermediates small: each folded input coefficient is below `10^56` in absolute
value. Even loose bounds allowing all alignment factors independently put
intermediate/output integer coefficients below 300 decimal digits. Thus this
domain does not approach Python's minimum configurable integer-to-string digit
limit of 640. Fallback inputs have the unchanged reference's behavior and are
not covered by that fast-domain size bound.

Removing only fractional trailing zero factors leaves the exact terminating
Fraction representation. Zero has coefficient zero and exponent zero; integer
values retain exponent zero. The Decimal tuple constructor performs no ambient
precision rounding. Its standard string conversion can still use scientific
notation for small adjusted exponents; fixed-point notation is not the same
wire contract.

## First RED retained, then a separately frozen wire-only correction

The first verifier was frozen at
`336eda6bc00b29be4663f9e64185bb7dc79786eb` and ran once on CPU 1 under a
10-second watchdog. It returned **RED / exit 1** in 0.385890758 seconds.
The complete [original stdout](../evidence/reviews/reserve-integer-independent/once01.stdout.json),
stderr and execution metadata are preserved at commit
`b661c224125dcf47f6495a83897c93ba5eb9a5fc`.

There were 72 recorded discrepancies: 36 from each implementation. Every one
has identical actual and expected Decimal tuples. The verifier had incorrectly
required its fixed-point description, for example `0.000000000000000022`,
where standard Decimal string conversion gives `2.2E-17`. The same discrepancy
appears for the unchanged reference. The [read-only adjudication](../evidence/reviews/reserve-integer-independent/once01-red-readonly-adjudication.json)
records that scope; it does not rewrite the first result or attribute the
verifier's representation error to candidate arithmetic.

A separately authorized revision was frozen at
`37d5e5417a95ac6bc546ce417ddafaf29386d458`. Its only oracle change is
`str(Decimal(expected_tuple))`, implemented in
[wire_contract_v2.py](../evidence/reviews/reserve-integer-independent/wire_contract_v2.py).
The Fraction formula, tuple expectation, vectors, branch checks and exception
checks remain unchanged. Neither production conversion function is reused.

The second, separately retained [execution](../evidence/reviews/reserve-integer-independent/once02.execution.json)
returned **PASS / exit 0** in 0.370234055 seconds, with no discrepancies:

| Check | Actual coverage |
|---|---:|
| Hand-entered component equalities | 96 across 16 cases |
| Independent rational value, Decimal tuple and string | 3352 vector/context evaluations |
| Distinct vectors per context | 838 |
| Ambient precisions | 1, 2, 9, 28 |
| Fast-path selections | 2968 |
| Out-of-domain delegated vector evaluations | 384 |
| Additional fallback/value/exception/delegation cases | 90 |

All four contexts also use exponent bounds `[-2,2]` and enable Inexact,
Rounded and Overflow traps. Cases include signed zeros, 38-digit coefficients,
exponents ±18, 39-digit/±19 fallback boundaries, settlement scales 0 and 18,
large mixed-scale products and a result with 54 fractional places. A fixed
seed supplies 400 additional signed vectors. The 90 separate compatibility
cases include all eight numeric fields receiving integers, strings, floats,
nonterminating Fractions, Decimal subclasses, NaNs/infinities and None;
nonstandard scales; a duck object and a missing object. Delegation is observed
without modifying either source file. Returned value/tuple/string or exception
type and text match the unchanged reference for those cases.

The complete [second stdout](../evidence/reviews/reserve-integer-independent/once02.stdout.json)
is 712 bytes, SHA256
`46df56d5d5e216739778446ea9acc73753c82e090a8b90a4e38988f64e70d6ea`.
Both runs preserve all three source hashes before/after. There was no SQL,
service invocation, financial state, network, signals or throughput load.
These short correctness runs and the author's separately labelled microprofile
do not demonstrate durable or mixed-load capacity.

## Compatibility limit requiring separate attention

The PASS scope uses plain `ReserveInputs` with stable fields, plus the listed
fallback objects. The entry guard uses `isinstance`, allowing custom subclasses
to enter the fast-path inspection. That inspection reads all eight numeric
attributes before computing reduce-only IM, whereas the old reference skips
reading the margin-rate attribute for reduce-only input. A subclass accessor
that raises on that field can therefore have different exception behavior.
This is a static Python-object compatibility edge, not an observed financial
failure; it was not executed in these two authorized runs and is not covered
by a blanket claim of all-subclass compatibility. An exact-type gate delegating
subclasses is one possible separate candidate. Ordinary immutable data fields
and Decimal-subclass fallback are covered by the recorded checks.

## Acceptance, deployment and rollback

This evidence supports the specified plain-input arithmetic scope only.
Integration still needs review of callers, product admission, current market
and rule versions, account reservations, persistence and replay; no flag is
enabled by this review. All production, real-funds, HA and persistent-10k flags
remain false. There is no migration, service restart or operational activation.
Revert the independent review commits to withdraw this verifier/report while
retaining both original runs and the unchanged reference. Do not overwrite the
first RED with the later PASS.
