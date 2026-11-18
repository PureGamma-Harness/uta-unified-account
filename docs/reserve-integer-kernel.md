# Exact decimal-integer reserve experiment

The current reserve expression constructs Fraction objects for every cold
arithmetic evaluation. This standalone alternative evaluates the same terms
using decimal coefficients and integer powers of ten. The existing Fraction
implementation, ReserveKernel cache, service callers, account admission and
durable reservations are unchanged. No feature flag or public trading operation
enables this candidate.

The expression remains: adverse execution loss=max(0, signed remaining quantity
times(limit-mark)); IM=zero for reduce-only, otherwise abs(remaining) times
max(mark,limit) times IM rate; unpaid fees=ceil((prior fee notional+abs(remaining)
times limit) times fee rate times settlement scale)/settlement scale minus
previously charged fees. Aggregate these exact terms before conversion. The
direction, cumulative fee ceiling and signed inputs are preserved; this
arithmetic function does not validate a financial order.

Fast-domain inputs are exact finite Decimal objects with at most38 coefficient
digits and exponents[-18,18], and exact integer settlement scale[0,18]. Other
inputs delegate to the unchanged reference, including its exception behavior.
Intermediate Python integers cannot overflow in this bounded domain. Decimal
construction removes trailing fractional zeros with integer operations,
matching the reference's Decimal tuple and wire string without consulting
ambient precision. No rounding is added to IM or adverse loss.

Before implementation, commitf826114 froze12 hand-recomputable examples,
including buy/sell adverse loss, reduce-only fees, partial fills with prior
charged fees, and an eight-decimal fee ceiling. Code
02c2193599f403dfe489b95e21123fcd1686ffc2 first passed4 pure test methods: those
manual cases,4,500 deterministic signed differential vectors under
precisions2/9/28,48 decimal-domain field boundaries, and reference fallback/error
cases. The reference core stays byte-identical. A separate Fraction oracle froze16 manual standards and verified3,352
value/tuple/string comparisons,96 manual components and90 fallback checks.
Its first72 wire-format mismatches affected candidate and reference equally;
the independent oracle format defect and original RED were retained before a
separately versioned correction. These component checks do not grant financial
model approval or trading permission.

A separate one-shot CPU1 microprofile compared three alternating pairs of12,000
pure calculations over the12 manual inputs. Reference53,349-68,598 calls/s;
candidate138,674-141,619 calls/s, approximately2.06-2.60 times in those short
samples. Result wire digests agree. These are short local arithmetic
measurements with synthetic repeated inputs; they exclude cache lookup, risk
reevaluation, queueing, matching, persistence, replication and network. They are
neither open-loop acceptance nor durable10k/s evidence. Full raw records and the
profile source are retained.

Deployment requires no schema migration or service restart because this module
has no production caller. Integration is separately gated on independent
reference checks, actual dispatch review, complete source validation, and
meaningful mixed/persistent benchmarks. Rollback removes experimental
imports/callers and retains the unchanged reference, results and manual
examples. Production, model approval, real funds, capacity and HA flags remain
false.

The independent group also identified a dynamic-subclass compatibility boundary.
Root preserved a real first counterexample at057fa65: a reduce-only subclass
raises when its unused margin attribute is eagerly read. Codec6a7210 delegates
all subclasses and duck-typed inputs immediately to the reference. The one new
regression passed; independent CODE/AST review8878056 confirms that only this
entry guard changed and the ordinary-input mathematics remained identical. The
old broad differential evidence binds02c2193; it was not rerun or relabelled as
a new complete-suite result for c6a7210. Integrated CI remains a separate gate.
