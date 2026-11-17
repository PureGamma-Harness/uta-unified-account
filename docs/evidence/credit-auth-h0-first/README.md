# Retained H0 author component evidence

Exact observed code is072cc77c5a96b48c81a143020ab8ac6c9a794a9b; original baseline is909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0. Read the scope summary and author report before interpreting PASS.

- `*-public-tests.json`: byte-identical original child files containing only explicit allowlisted test identifiers, statuses and bounded error codes. No live key/nonce/signature/database bytes.
- `*-execution.json`: explicit allowlist from the original private execution record, including source hashes, actual runtime command template, clocks, affinity through child results, watchdog, exit and original raw hashes. The two private command positions are replaced structurally; original exact invocations remain private.
- `*-runner-source.py` and both driver sources: exact code bytes with verified original SHA. They contain runtime secret generation, never generated secret values.
- `scope-summary.json`: exact runtime delta and remaining verification gaps. Neither component PASS nor these files authorize financial execution or production.
- `manifest.json`: SHA/length index of public artifacts at first collection. This README is a later descriptive index; it does not rewrite any original artifact.

All raw streams/private runners/keys/authorities remain under `/workspace/uta-auth-h0-private`, protected by0700 directories and0600 private files. Root and an explicitly authorized independent verifier may inspect them. Original raw is never overwritten or rerun to change an outcome.
