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

Initial delivery137562a0 merged the independently reviewed PR46 MM fixture
correction and verified all66 SQL4 retained inputs plus the caller equal the
actually executed sourceb4151847. That remains historical evidence. Its first
normal push/PR CI failed all8 jobs: each2066 tests/1 failure/16 errors. Eight
375-pin maps and original failure stacks are independently bound by a59e1d41;
all package/build/installed stages were absent or skipped. Preserve these
failures and do not treat eleven new passing method IDs as platform acceptance.

The corrected candidate separates the ten-field runtime valuation policy from
the order envelope's additional admission contract. Credit-v2 keeps its original
persisted reconstruction and exact equality; no unknown fields are dropped.
Independent CODE54220955 verified this narrow change and the four new pure
contract tests, which have not yet run locally. No financial formula, DDL,
borrow mutation, format or historical archive is changed. Corrected-source
normal CI, including the original credit helper and restart failures, is pending.

The corrected runtime now also changes credit_audit_v2.py relative to PR46.
Its artifact differs from b4151847, so original SQL4 results are not relabeled
as a new-source run. Old certificates and failed first results retain their
actual source identities; existing-authority hot replacement remains unsupported.

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
