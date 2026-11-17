# H0 data-fix first author evidence

Observed runtime source is61258109e10f4ea4609e03010d5f25716b2c4256. This directory contains only explicit allowlisted results, execution metadata, exact runner/driver code and SHA manifests. All private raw/request/key/DB data remains outside Git.

- Three `*-public-tests.json` files are the original allowlisted child results:19 methods per runtime,0 failures/errors/skips.
- Three `*-execution.json` files retain actual source/test identities, clocks, exits, command templates and hashes of private raw. Private runner/output positions are structurally replaced; original exact commands remain private. Generated signed-request counts describe generated inputs, not every later deliberately mutated invocation.
- `original-data-read-result.json` is the original safe constructor result. Its paired execution metadata explicitly limits the file guard to main DB bytes and states that read-only flags were not independently instrumented.
- Runner/driver and original-data-reader code match the actual recorded SHA. The old driver sources are retained unchanged in the earlier evidence directory.
- `scope-summary.json` and the author report keep independent/full-H0/release/production acceptance false. `manifest.json` indexes first collected artifacts; this later index does not rewrite original outputs.

No original072 PASS, independent RED, private authority or frozen909 was modified. Do not retarget old hardcoded source probes and keep their old source labels; future runs require a new source-bound artifact and output directory.
