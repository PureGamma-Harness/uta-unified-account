# Offline deployment lint: source-bound first results

The first source `f40629da7d0bd8acab221c3f42d35b9a7d4ce5e2` ran16 metadata
tests successfully in20,785,959ns. After explicit uninitialized source/artifact
reference refusals were added, source `c690c2e` ran17 tests successfully in
37,439,954ns. These are the measured test intervals before result serialization,
not complete supervisor wall intervals or deployment latency claims.

Both original runs used Python3.12.14 on CPU2, captured source hashes/import
paths in the same test PID, and hard-mocked SQL connections, child-process
creation and signal calls during tests. The runner's pre-test Git identity read
is a separate read-only metadata command. Fixtures were newly created opaque
synthetic files; the checker read only their metadata. No SQLite database,
secret/profile or wheel body was opened. Raw streams and drivers remain private;
their original hashes and byte lengths are recorded here.

Latest source `b88bd49` additionally adds NUL and invalid UTF-8 path refusals plus
the corresponding two subcases. Its two Python files were parsed with the
Python3.10 grammar, but these new subcases and a complete test of that latest
source remain **NOT_RUN**. Root requested no further testing while the separate
full QA storage reserve was narrow. Earlier passing source results are not
silently promoted to this new source.

The files here retain separate original source proofs, results and aggregate
scope. They prove no actual release bytes, service deployment, approval,
replication, recovery, financial authority or production readiness. See
`docs/offline-deployment-manifest.md` for the tool's explicit limitations,
deployment use and removal-only rollback procedure.
