# Market control revision 2: third source delivery

This candidate retains the runtime and market-control behavior of source
8faa56d5fcfcd1b176cbb1c2d8e142986f56ab15. Its runtime inventory remains 65
Python files and one HTML file, 1,470,877 bytes. No runtime, financial schema,
fault-test source, native capture fixture or workflow configuration changes.

The first source 72dd3a17 failed all eight jobs in runs 44336268341 and
44336471937: each summary reported 2,193 tests, three failures and one error.
The corrected source 8faa56d5 failed all eight jobs in runs 44342181511 and
44342194604: each summary reported 2,193 tests, two failures and zero errors.
Both scopes remain immutable failures. Neither is replaced by this candidate.

The remaining two failures invoke the same full-module AST guard. Source
fadd182da051ee84681f1c77734543d33751e3e5 preserves the original complete
reference and allows exactly one reviewed method version before applying the
same complete-module check. A new negative test requires the actual guard to
reject changes to either that method or protected recovery. Independent review
944d9561e7456d28d51ef35444833c53e890f42d found no static blocker; its evidence
is source/AST data inspection, not executed tests or a CI result.

## Deployment and acceptance

Use a fresh isolated synthetic authority and the existing phase-one deployment
instructions. The standard workflow must run independently on the exact new
head, across Python 3.10 through 3.13. Preserve the first push and pull-request
runs separately, including failed logs and artifacts. No local financial
imports, SQL, actors, native capture or target tests were run for this delta.
CI remains pending at this commit. Passing CI would close only that source's
workflow gate; it cannot establish capacity, replicated recovery or production.

The separate component pure/SQL capture, installed-component functional tests,
pending-funding holds, urgent-operation queue capacity, exchange product scope,
full matching reconciliation and sustained capacity gates remain OPEN.

## Rollback

Revert the exact allowance, negative test and related documentation to the
previous reviewed source. Keep both original failed scopes and the original
reference file. No migration or automatic reseal is required by this delta.
Preserve confirmed command, trade, position and journal history; reconcile
unknown effects before any wider runtime rollback. Do not restore a historical
account snapshot over confirmed trading effects. Production and real-funds
activation remain NO_GO.
