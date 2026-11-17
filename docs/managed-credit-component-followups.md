# Credit component follow-up scope

The `59a7b32` component raw results remain immutable, including its placeholder
decision identity and ten green primitive checks. The follow-up changes only
the component identity to the existing base canonical decision hash and adds a
positive `DecisionAudit.decision()` read check. That proves the base reader can
retrieve this SQL component record; it supplies neither a complete credit
artifact nor a credit operation replay.

The debt trigger is deliberately only `BEFORE INSERT`, with the specific
opening-zero to BTC .4 transition. It does not verify an increment on existing
principal, UPDATE/DELETE, REPAY, opening-interest disposition, active dispatcher
context or authorization lifetime. The 59 snapshots already included account
versions as `accounts`; no version-preservation claim is inferred merely from
the cash projection.

Given expected legs are fixture input; canonical generation, amount↔units
coherence, per-CID unique first source, the full native credit UDF and immediate
protected-DDL authorizer are still absent. In particular, matching two equally
wrong expected/actual sets is not independent proof of a sanctioned loan.

The initial microtest assertions read native SQLite extended-code attributes.
Their 3.12 results are actual native-code evidence. CPython 3.10 does not expose
those attributes, so this exploratory test file needs a separately reviewed
portable classification before joining a future full runtime matrix. It must
never translate SQLite_ERROR/OperationalError into successful denial, skip the
case or report an inferred code as an observed native one. No multi-runtime
pass is claimed here.

No runtime, route, DDL installer, prior source, raw log, frozen code or active
job changes. Production/runtime remain NO-GO. Only the necessary new positive
component case will run for the canonical identity change; this is not a rerun
to overwrite the 59 result or expand its ten-case acceptance.
