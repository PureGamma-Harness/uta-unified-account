# Official runtime preparation evidence

`provenance.json` contains the selected official manifest entry and release asset.
The original archive remains outside Git. `prepare_runtime.py` is the exact
initial extraction/preparation driver, retained after its strict version assertion
failed. `initial-version.*`, `capability.*` and `initial-failure.json` preserve
the observed host3.13.5 library mix. Its exception trace was emitted directly by
the tool rather than redirected to a new log; no fabricated stderr copy is added.

`bundled-capability-command.json` and `bundled-capability.*` record the first
correctly scoped shared-library check. `verify_prepared.py`,
`preparation-result.json` and `final-capability.*` record the final read-only
archive/member/environment/loaded-library/child-version checks. No SQL database
was opened and no trading case or service ran.

Only public provider metadata, preparation code and allowlisted capability
outputs are committed. No runtime binary, archive, credential, database,
signed download URL, old-job state or financial command is included.
