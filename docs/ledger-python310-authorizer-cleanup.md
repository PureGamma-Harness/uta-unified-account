# Python 3.10 ledger fixture authorization cleanup

The final combined source `dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b` is rejected by its original CI: both Python 3.10 jobs completed 1801 tests with eleven errors. Their original logs are preserved in independent commit `653270d9d41b5cbbd910f4a3d7e05899cde0efd7`. The other six jobs passing does not qualify that source.

The errors occur after the intended ledger verification, when two raw-connection test fixtures call `set_authorizer(None)` and then inspect the caller's unchanged state. The Python 3.10 API treats that cleanup as an unusable callback, so subsequent SQL is rejected. An independent scalar comparison uses the same SQLite 3.53.1 with Python 3.10.22 and 3.12.14: only 3.10 rejects the SELECT after `None`. Python 3.13.5 / SQLite 3.46.1 accepts it. An explicit callable returning `SQLITE_OK` permits the post-check on all three.

The patch changes two test cleanup calls to explicit permissive callbacks, after the strict verification callback has completed. TEMP reads remain denied during verification. Every existing corruption, transaction, state equality, native managed-read, foreign-path and rollback assertion is retained. All 62 tracked runtime files are byte-identical to dbc93e5. No production authorizer, SQL, permissions or financial calculation changes.

The original 26-test local target run reproduced all eleven errors in 0.524 seconds. With this patch the same 26 tests passed once on each of Python 3.10, 3.12 and 3.13 in 0.517, 0.516 and 0.515 seconds respectively. Commands, runtime probe code, cwd, timestamps, hashes and unedited stdout/stderr are in `evidence/runs/ledger-python310-authorizer-cleanup/`. These are targeted synthetic fixture tests; full tests, CI, packaging and independent review of the successor source remain required.

Deployment: this change modifies tests only and installs no runtime behavior. Rollback: revert this commit if needed; that restores the known Python 3.10 test incompatibility. No database migration or rewrite is required. Original dbc93e5 evidence and source remain immutable; no production approval is granted.
