# Python3.10 test cleanup: narrow independent acceptance

Independent file/Git/AST review accepts only the two test-cleanup changes in
`5ff974d7cf32715452c4d205efa748e4e4b59f23`, relative to
`dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b`. Both replace
`connection.set_authorizer(None)` with a callable returning SQLITE_OK inside
the raw fixture's existing finally block. Normalizing just that argument in
each file restores its complete original AST. All original assertions, strict
TEMP-denying callbacks, error expectations and transaction/state checks remain
identical. No tests are removed, filtered, skipped or given new expected errors.

The permissive cleanup occurs after the original verifier call has returned or
raised, so it does not weaken the authorizer used during verification. It
allows the fixture's subsequent snapshot/query_only assertions to execute on
Python3.10. An unexpected verifier failure still propagates; no new catch or
fallback was added. Managed native authorizers are not replaced in the native
read-role control. All62 runtime Git blobs are byte-identical to dbc93e5, with
runtime digest `ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`.
This changes no production SQL, permission, API or financial calculation.

The retained first-party [Python3.11 documentation](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.set_authorizer)
says: “Changed in version 3.11: Added support for disabling the authorizer using
None.” Root recorded HTTP200 at2026-11-17T16:52:40.898990Z; independent file
review verified all271807 HTML bytes and SHA256
`d85840c64dce31026a463e64234e4d395bfaa71fadc3475a9d3eec50f9fba61a`,
and checked the exact section exists in those bytes. The original scalar
records agree: Python3.10.22 and3.12.14 both used SQLite3.53.1; only3.10
rejected the SELECT after None. Explicit SQLITE_OK passed on3.10,3.12 and3.13.
No document was fetched and no scalar was executed by this reviewer.

Original CI evidence at653270d remains NO_GO: both Python3.10 runs completed
1801 tests with11 errors, zero failures/skips. The original six raw file hashes,
summary/worker/log correspondence, all eleven error headers and all348
before/after input hashes per report were independently checked. The errors
occur in post-verification query_only/snapshot checks. The original local
26-test baseline also retained its11 errors and exit1 (outer0.524s). The three
patched26-test author runs have exit0 and no failures/errors/skips, with outer
walls0.517s,0.516s and0.515s. Those author runs preceded the commit on an
explicit dirty test-only patch; both recorded test hashes match exact5ff974d.
They are targeted results, not an independent rerun or full-source acceptance.

The PR merge object4c78b658 is not present locally. Its348 actual input hashes
were checked against dbc Git blobs; its tree equality is supported by the
retained provider metadata, whose tree9b30f41b matches the actual local dbc
tree. A local PR merge-object verification is not claimed. The first file-audit
attempt stopped at that unavailable-object assumption; its original checker
and complete error output remain preserved. The corrected file-only review
records this narrower provenance explicitly and reruns no SQL or tests.

The [report](../evidence/reviews/ledger-python310-cleanup/review.json) contains
the exact AST identities, runtime hashes, original error names and author
commands/cwd/timestamps/raw checksums. No original source, raw report, database
or prior package result was edited. Final successor-source full QA, CI and
packaging remain required. Overall status remains NO_GO; no deployment,
smoke/long preflight or production approval follows.
