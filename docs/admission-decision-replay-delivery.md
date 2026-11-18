# Order admission decision replay delivery

Orders accepted by the local service now archive the admission projection,
fee/PnL, original order operation, risk/control state and version provenance.
Replay distinguishes numerical valuation from admission eligibility, so
matching risk values alone cannot claim that an order was permitted. Ordinary
orders and reduce-only orders have explicit coverage. Fills retain numerical
replay while admission replay reports UNSUPPORTED for that decision kind.

Missing old admission certificates remain UNSUPPORTED. Consistent non-boolean
halt values and altered fee certificates fail verification. Coexisting old/new
policy candidates reject automatic source reconstruction. This is a fresh
authority candidate; schema3/format1 remaining unchanged does not make old
policy deployment or migration supported.

The independent account/risk CODE review, unique PURE7 run and RAW05d060a4,
and SQL4 ENTRY review16323e86 precede the unique SQL4 run atb4151847. That run
passed4 fixed methods/0 failures/errors/skips, using4 fresh synthetic DBs,
5 journal events,3 orders,1 unpaired local fill and4 decisions. Three accepted
orders replay VERIFIED; the fill's admission replay stays UNSUPPORTED.
The local fill charges USD0.02 and leaves quantity0.5/cost50 and reserve5.04.

Independent RAWba7b6a4e checked30 sealed originals3058968B and all archive
members, then decoded actual SQLite table B-trees/records directly without
SQLite connections or target imports. It independently recomputed each
posting/hashchain, full balances and signed orders, fee/cost/reserve and
decision before/after/projections. Four real read-role DML attempts were
denied and poisoned commit; schema/rows/main bytes stayed unchanged.
All105 observed native connection handles were already closed before cleanup.
Actual target, outer and caller exits were0 with EOF/reap and no rescue cleanup.

Target interval940216051ns, inner719354757ns, tests397088601ns and caller
through validation1555341844ns have distinct scopes. Tool yield/poll durations
are not summed into an end-to-end latency. These figures are not capacity.

This delivery merges the independently reviewed MM fixture correction from
PR46; all66 retained SQL4 inputs plus the caller remain byte-identical to the
actually executed sourceb4151847. The only runtime changes relative to PR46
are the admission capture and decision replay changes in service/decision_audit.
Historical first evidence remains pinned to its original SHA. First normal
CI of this delivery is pending.

Deploy only into new explicit synthetic authorities with the archived
constructor policy. Existing-source ambiguity must reject, not select or
rewrite a policy. No product mode, managed authority, migration or default
funding behavior is enabled. Rollback removes the candidate in a fresh
environment; never roll back confirmed economic history or erase old audit
records. Preserve all evidence and reconcile confirmed operations before an
authority handoff.

Configured Cross valuation still uses the production numerical engine, with
a separately derived admission predicate/manual constants. This does not
accept an independent full Cross model, paired matching, concurrency/fault
recovery, performance, HA, custody or production/real-funds enablement.
