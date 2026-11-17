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

The next component-only patch adds a strict portable category: when native
attributes exist, the actual numeric extended code remains mandatory. Only
when those attributes are absent can an exact builtin IntegrityError and a
fixed known constraint-message signature classify the result. It preserves
`sqlite_errorcode=null` and labels the evidence as message classification,
never an observed 787/1299/275/1811. Unknown messages, OperationalError and FK
mismatch remain failures. Its new results must be recorded independently.

No runtime, route, DDL installer, prior source, raw log, frozen code or active
job changes. Production/runtime remain NO-GO. Only the necessary new positive
component case will run for the canonical identity change; this is not a rerun
to overwrite the 59 result or expand its ten-case acceptance.

## Actual follow-up results

Frozen component source `daea6814a2fbcbcabc787e09d693c001df5025b0` ran on CPU3 at
**2026-11-17 10:52:44.034244–10:52:48.059698 UTC**. The necessary 3.12 canonical
positive case passed and the base decision reader actually returned its canonical
ID/account/kind/version fields. Then the 3.10 microfile passed all ten tests,
including the real old binary controls, once. No 3.12 full microfile or 3.13 run
was repeated or claimed. New window4.025737s; combined actual probe time with
the original window is7.997538s, below the predeclared30s budget.

The 3.10 error observations preserve `sqlite_errorcode=null`, native attribute
absent, and the explicit exact-message classification basis. The original 59
3.12 evidence retains its observed numeric codes. Both remain separate source
and runtime evidence; there is no fabricated native code or test skip.

[Commands, time and raw observations](../evidence/runs/credit-obligation-component-daea681/execution.json)
include all actual results and cleaned temporary authorities. Credit runtime,
complete credit audit/replay, native context/authorizer and first-source budget
contracts remain unimplemented and NO-GO.
