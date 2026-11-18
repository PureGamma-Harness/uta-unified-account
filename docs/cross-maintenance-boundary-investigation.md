# Cross maintenance equality: static investigation

Status: first bounded pure calculation completed on corrected source
`402c78412df53cb91e0f7f7d463fdd7026cf7cac`; independent RAW review is pending.
Six methods completed fifteen named manual cases with no failures, errors or
skips. No actual service admission, fill, SQL, worker, benchmark or native probe
has run for this investigation. The base is
PR35 commit `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`. Current main
`02549e5d662caa7156dc30e95f1d5e2dce18215c` does not contain the configured Cross
service; evidence for this branch must not be attributed to main.

This is a local policy issue under `UTA-CROSS-LOAN-v1`, rather than a claim
about another exchange. [The existing rules](margin-rules.md) allow initial
margin availability equal to zero but classify risk equity equal to maintenance
margin as `LIQUIDATION`, including the zero-MM boundary.

Local rule trace: `UTA-CROSS-MM-STRICT-001`, derived from the existing
`UTA-CROSS-LOAN-v1` maintenance trigger in this repository. This patch applies
the already documented strict trigger to fresh ordinary linear admission and
execution, rather than introducing an exchange margin formula.

## Observed source path

`LinearMarginRule` permits `0 <= MM <= IM` with `IM > 0`. The service's market
validation additionally requires positive IM and MM, but still permits equal
rates. For a new ordinary order, `_admit_order` rejects only when available
margin is less than the new reserve. For a fresh ordinary fill, `_apply_fill`
rejects only when projected availability less the remaining reserve is
negative. Neither currently tests strict projected maintenance surplus.

A hand-computed, synthetic boundary is one USD-settled linear contract at mark
and limit 100, multiplier one, quantity +1, IM and MM rates both 0.1, the default
fee rate 0.0004, and USD cash 10.04. There are no other positions, loans or
orders. The new reserve is `100 * 0.1 + 100 * 0.0004 = 10.04`, so the existing
admission comparison permits equality. A complete fill charges 0.04 and leaves
equity 10, IM 10, MM 10 and availability zero. The existing fill comparison
permits equality while the configured Cross calculator classifies that state
as `LIQUIDATION`. These are static source deductions and manual values, not
observed execution results.

The candidate retains the original initial-margin reserve rejection first,
then revalues **every** ordinary new order at its limit price with exact
settlement PnL and ceiling fee. Projected risk equity must be strictly greater
than projected MM. A fresh ordinary fill uses its already calculated projected
risk and applies the same check after the existing IM/remainder check. Both
reject through `insufficient_margin`, HTTP 409. The two call sites share one
`_require_maintenance_surplus` helper using exact `Fraction` values.

This adds one full risk calculation to each ordinary new-order admission that
passes the original reserve test. No extra calculation is added to the fill
path. Performance for this candidate is NOT_ACCEPTED. An equality-only admission
optimization was deliberately omitted: the general proof must also cover
cumulative fee ceilings, full-close PnL floors, legitimate cost dust, other live
orders, frozen assets and debt before it can remove that projected calculation.

The intended correction must retain the initial-margin equality boundary when
MM is strictly below IM. It must preserve the independent reduce-only surplus
policy: an account already under liquidation can require reducing fills without
first restoring a positive maintenance surplus. It must also preserve lookup
of previously confirmed order/fill IDs before new admission checks; historical
confirmed effects cannot be retrospectively rejected or posted twice.

## Rejected cost-sign hypothesis

An earlier hypothesis suggested requiring every nonflat `LinearExposure` to
have nonzero entry cost with the same sign as quantity, following the separate
research `Position.entry_notional` input rule. The service settlement path
disproves that hypothesis. `_project_fill` lines 889–895 deliberately retain
settlement rounding dust in surviving position cost:

```text
exact_pnl = sign * closed * execution - old_cost * closed / abs(old_quantity)
pnl = floor_to_USD_units(exact_pnl)
surviving_cost = old_cost - sign * closed * execution + pnl
```

A tiny surviving cost can legitimately cross zero; the next close must retain
its sign. Realized PnL is posted to cash, with the unsettled rounding remainder
carried in cost. `tests/test_service.py` already covers the tiny-position
settlement sequence. The Cross cost field therefore differs from an untouched
signed opening notional. No sign restriction was implemented and no historical
position was modified. A position's apparent sign mismatch alone is insufficient
evidence of corrupted cost.

## Execution and delivery gates

The corrected pure driver received independent CODE review
`c269409ba19ee2b3103214bbd12ad88708d27329` before root authorized its unique
first bounded test. [Its preserved evidence](../evidence/reviews/cross-maintenance-boundary/first-pure-402c784/README.md)
records the exact source, plan, six methods/fifteen cases, raw streams, actual
CPU and runtime, actual prefix exit0/reap, and unchanged input bytes/metadata.
The selected calculation interval is 79,838,698 ns; the actual timeout/taskset
Popen-to-wait interval is separately 293,413,990 ns. This is a conditional pure
PASS, pending independent RAW closure. A pure calculation/helper result alone
does not establish durable rejection, transaction rollback, partial-fill
behavior or matching integration; those require a separately scoped fresh
SQLite/service validation. The benchmark scope on another source cannot be
borrowed. Production, real funds and product activation remain unapproved.

The completed first pure scope contains six methods and fifteen named,
hand-computed case completions in `tests/test_cross_maintenance_boundary.py`:
fee-inclusive equal IM/MM; the eight-decimal USD units immediately below, at
and above MM; valid IM equality with lower MM; safe partial and unsafe final
fill projections; zero MM with zero, negative and positive equity; and the
three existing reduce-only surplus outcomes. Two additional manual evaluations
bind the same boundary to `ExchangeService`'s `legacy_reference` risk values,
which share these guard call sites; the standalone demo `check_order` function
is unchanged. Selected service methods are the
unchanged reserve, projection, rounded-fee and RO helpers plus the new strict
helper. Six pinned risk/model modules execute from retained verified bytes.
The service module, its constructors, SQL methods, `_admit_order`, `_apply_fill`,
cumulative `_fill_fee`, matching, API and process workers do not execute.

Static integration review must separately confirm that both new guard calls
are exclusively in the non-RO branches, and that the original prior-ID returns
and original RO subtree remain unchanged. Those source checks are not durable
idempotency or transaction tests. The once driver retains shared
256 KiB raw capacity including a 512-byte failure trailer, refuses incomplete
raw writes, uses an exclusive new 0700/0600 output namespace, and records its
inner completion; the caller must record the actual hard-timeout/taskset argv,
exit/reap and elapsed time. This reviewed pure program is not an OS sandbox.

There is no proposed database schema or data migration. A rollout would use new
synthetic, code-bound authorities first; an existing authority must follow its
code/layout handoff policy. Rollback retains all commands, accepted receipts,
confirmed fills and journal entries. It cannot erase confirmed effects or retry
an unknown result under a new business ID.

Independent review caught a preparation defect before execution at source7c8bf60:
the selected service AST omitted its original future annotations import. The
driver now retains that exact AST node, preserving annotation semantics without
loading SQL/native imports. The original plan is retained byte-for-byte as
`once-plan-7c8bf60-NOT_RUN.json`; it had zero target attempts and was not a test
failure. The new plan rebinds only the corrected driver. Financial service code,
six model modules and all manual expectations are unchanged by this correction.
