# Independent review of strict maintenance surplus

This is a CODE_ONLY CLOSED result for the proposed six-method, fifteen-case
memory-only calculation run on source
`402c78412df53cb91e0f7f7d463fdd7026cf7cac`, tree
`b46d501957167368c224e9040186d8c469fc67a2`. It does not authorize or establish
service admission, fills, SQLite, audit replay, matching, performance or product
activation. No target was imported, compiled or executed during this review.
The plan SHA-256 is
`92fc36f7c1ea2f98d91f518fe93667c4a8ad907600a8e32c0070631c34fdcdc6`.

The base is PR35 at `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`. All nine
materialized regular input files equal their plan lengths, SHA-256 values and
frozen Git blobs: 169,890 bytes in total. The accompanying JSON records those
pins. Read-only metadata processing used standard-library AST parsing and Git
source reads; it did not compile or execute selected target definitions.

## Rule and patch

The existing `docs/margin-rules.md:38` makes risk equity equal to maintenance
margin a liquidation boundary, including zero MM. Initial-margin availability
may still equal zero. The example has cash 10.04, quantity 1 at mark/limit 100,
IM = MM = 0.1 and fee rate 0.0004. Reserve 10.04 passes the previous IM check;
fee 0.04 leaves equity 10, IM 10, MM 10 and availability 0. The new strict
comparison rejects this boundary with `insufficient_margin`, status 409.
With MM 0.05, the same equity 10 and IM availability 0 retain MM surplus 5 and
remain eligible under this added comparison.

In `uta/service.py:812`, every ordinary new order that passes the original IM
comparison receives a complete limit-price projection and rounded PnL/fee
balance delta. The new helper at line 860 compares exact Fraction values. In
the configured Cross branch, `_risk` maps its `equity` field to `risk_equity`
at line 555. The ordinary fill call at line 988 uses its existing projected
risk after the original availability/remainder-reserve comparison.

Removing precisely the new helper, the ordinary admission projection branch
and the fill helper call produces the complete original service module AST.
The six model/risk modules are byte-identical to the base. Original prior-ID
returns, reduce-only branches, SQL statements, cumulative fee calculation,
projection rounding and legitimate signed cost dust therefore remain intact.
No cost-sign restriction was introduced.

The fifteen literal expected cases correctly distinguish MM minus/equal/plus
one USD settlement unit; IM equality with lower MM; zero MM with nonpositive
versus positive equity; partial/final projections; three nonworsening
reduce-only outcomes; and both legacy reference boundaries. These constants
are hand derived, not produced by an expected-value call to service logic.
The partial projection test does not execute `_fill_fee` or remaining-order
reserve handling. Their unchanged source uses cumulative notional ceiling
minus previously charged fee; durable fragmentation remains an integration
acceptance requirement.

## Compatibility changes requiring explicit acceptance

Admission now projects the entire proposed quantity. `_project_fill` at line
895 can raise `position_limit` before accepting an order whose complete
projected position exceeds the existing limit, even if a smaller partial fill
could have been valid. This is an earlier existing rejection, not an unchanged
error contract.

For configured Cross accounts, the added `_risk` calls `calculate_cross_risk`
with another `self._now()` at lines 544-545. A market can cross its age limit
after the original market/current-risk checks and now fail closed earlier as
`risk_unavailable`. The legacy `_risk` branch has no such added freshness
validation. Legacy ordinary service admission/fill still gain the strict
equity/MM comparison; the standalone demo calculation remains unchanged.

Each IM-sufficient ordinary admission adds a full account risk revaluation,
with additional database reads and CPU/allocation work. Fill reuses its
existing projection. Performance is NOT_ACCEPTED; this review does not grant
timing equivalence or extend a deadline.

## Audit integration remains OPEN

`DecisionAudit.validate` at lines 245-260 validates archive schema and guards.
`DecisionAudit.replay` at lines 396-441 expressly performs numerical valuation,
not admission eligibility, ownership or historical clock checks. It recomputes
before/after risk and ORDER reserve; it contains neither an old IM admission
validator nor the new strict MM admission predicate. Ordinary ORDER evidence
still records `projected_execution=None` in `service.py:837`. FILL evidence
records actual before/after risk at lines 1025-1029. Therefore replay
`matches=true` cannot demonstrate that a command passed the new strict rule.
This is a limit of the existing replay contract, not evidence that numerical
replay must change its old artifact format.

The artifact mechanism includes deployed service source and loaded class
methods, including this static helper (`decision_audit.py:118-167`). A changed
engine cannot authoritatively replay an older decision with its new binary;
the old matching source/runtime must remain available. No archive format or
historical evidence was changed by this patch or this review.

Before claiming the full chain is accepted, a separately authorized fresh
synthetic SQLite/service exercise must check actual ORDER/FILL acceptance and
rejection, no decision/journal/version mutation on rejection, durable prior-ID
receipts, cumulative partial fees/remainder reserve, RO behavior, legacy mode,
earlier position-limit and freshness behavior. Actual accepted ORDER/FILL
archives must be checked with independent arithmetic for the strict predicate
and before/after values, then with the matching-source numerical replay after
later account/market changes. Production helpers must not generate that
independent oracle. A full-fill unsafe-at-admission case must not be presented
as an actually admitted partial-fill scenario. This review neither supplies
nor executes that fresh exercise.

## Once driver and protected first result

Source `7c8bf6055db86ff8267831c80bd75ca837a60dbd` had a preparation blocker:
the driver dropped the original future-annotations AST node, leaving a
`MarketSnapshot` annotation unbound. It remains NOT_RUN with zero attempts,
not a runtime RED. Its original plan is preserved at SHA-256
`f9836976c789f6208b7fe98e7c6979219168e474677f412e4040cabab7b0d065`.
The sole 402c correction retains the exact original future node first and
requires its only imported name to be `annotations`; it does not inject a
fake annotation type or alter financial expectations.

The retained closure is six model modules and six selected service methods.
Their globals and passive standard-library dependencies are present. The
fixture has six explicitly selected methods and fifteen ordered completion
IDs, with no discovery or inherited-method expansion. The driver checks the
actual pinned executable/runtime/flags and affinity `[1]`, retains verified
input bytes for execution, and rechecks source/plan bytes afterward.

The proposed host command uses `timeout --signal=KILL 10s`, `taskset -c 1`
and the pinned Python with `-I -S -B`. The host must separately preserve actual
argv, exit, reap and elapsed time. A new private directory and O_EXCL 0600
captures prevent overwriting a first result. Reviewed Python output reserves
bytes before descriptor writes under one 256-KiB shared ceiling with a
512-byte failure trailer; overflow/incomplete writes terminate as 125.
This is a bounded reviewed program, not an OS sandbox against arbitrary
native descriptor writes. An inner receipt alone is insufficient: acceptance
must require complete BEGIN/END/raw and actual host success/reap, with no
automatic retry on failure, timeout or unknown result.

This independent worktree adds only its own review files. The author source,
old review records and all prior first-result evidence remain unchanged.
The first pure run still requires root's exact-source authorization.
