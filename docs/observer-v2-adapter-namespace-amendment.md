# Adapter proposal source amendment, still NOT_RUN

This supersedes the executable source/unique path in the unrun3e42 proposal,
without editing that original plan or its source-budget record. During CODE
inspection the actual extracted controller `append` was found to call
`ro.canonical`; the restricted adapter namespace had not provided that helper.
It would fail at first publication. No execution, failure result or retry
occurred. Commit `dc1e8e6c37e98a0d33c7d2aafc8af96ffca7ee4d` adds that
canonical helper, using the same strict codec as the actual injected parser.
No controller, report codec, verifier or transport behavior changes here.

The new runtime-input freeze is
`dc1e8e6c37e98a0d33c7d2aafc8af96ffca7ee4d`; the eight-file closure and exact
new proposed argv are in
`evidence/observer-compact-report-v2/adapter-preparation-dc1e/source-budget.json`.
Probe SHA256 is
`011e8c97cc641110dab797da2f4d569fa43ea05798e29f70e5b42458fc95b7d3`.
The fresh proposed output is now
`/workspace/uta-observer-v2-adapter-runs/read1-dc1e8e6-once01`.

Every bound, evidence requirement, prohibition, rollback instruction and
limitation from `observer-v2-adapter-first-plan.md` remains applicable with
these superseding identities. In particular this is CODE/PREP, all adapter
execution is NOT_RUN, original mock12 evidence is unchanged, no observer/SQL
or old-data access is authorized and `allowed_runs_without_further_root_go=0`.
A later separate root GO must identify this new source and one-run scope.
