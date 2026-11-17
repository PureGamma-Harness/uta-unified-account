# Independent credit reference review

Runtime:44a25b21fca1c6b86e68c05d2620a01ca3b8b04f. Runtime files remain unchanged.
The new independent test file is an untracked working input during these runs;
its exact SHA and before/after runtime map are in multiruntime-manifest.json.
This is targeted independent verification, not a clean full-release report.

initial-python312.txt:7 cases,6 pass/1 ERROR because the synthetic product was
left at default DISABLED; it never reached the intended order margin operation.
Only that fixture status was corrected to ACTIVE. fixed-python312.txt is the
first7/7 success. python{310,312,313}-final.txt are the subsequent identical
source test runs, one CPU, ResourceWarning treated as error,7/7 each.
original-three-repayment-fixtures.txt reruns the three existing repayment cases
whose loan bootstrap moved before fencing; all3 pass.

static-review.json records AST equality of the old financial body and A1 joined
body, unchanged _prepare and the existing join helper. Test code contains an
independent integer journal and explicit Fraction hand formulas; no production
risk, ledger/replay or rounding function supplies expected values.

No runtime, schema, financial policy, old job, secret profile or live authority
was changed. No capacity, HA, long-run or production approval is granted.
