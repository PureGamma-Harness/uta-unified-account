# Credit verifier alias: narrow static acceptance

Independent review accepts only compatibility commit
`060022cd3050e2ffc0af50aece26d2ab57e90bd4`, reviewed against parent
`fbfbfeabc65a05af47ad510bd600d7f1f404b064` and current tree460d04d. Removing
the one new static alias recovers the original whole `credit_native.py` AST.
The aliased helper's AST equals the separately accepted F01 checker.

`DurableLedger.verify(ledger, connection=connection)` still joins the caller's
same connection. The new `staticmethod(DurableLedger._verify_postings_definition)`
receives that current connection without binding a view instance as an extra
argument. It adds no constructor, transaction, DDL, role, verified flag, fallback,
positive callback or mathematical change. Its accepted schema scope remains
the persistent MAIN postings definition; TEMP/F02 and other provenance gaps
remain separate.

The existing artifact scan includes credit_native and storage. It traverses
the local view class, unwraps `staticmethod.__func__`, and fingerprints the
actual alias code, unwrapped code, defaults and closure under
`uta.credit_native._LedgerVerificationView._verify_postings_definition`.
The original storage helper and `storage._SCHEMA` are independently covered.
A second static peer reached the same conclusion. The two new integration
tests do not explicitly assert this identity key; adding that assertion at a
future authorized gate would strengthen regression coverage.

The canonical control invokes the original complete verifier on a real read
snapshot, checks query_only remains1, compares all logical rows/catalogue and
rejects DDL/DML in its trace. The negative fixture preserves its original
postings and guards while removing only the event FK, then checks the exact
`LedgerError("journal postings table definition changed")` cause under
`credit_financial_source_invalid`. The existing fresh-source target actually
installs the capability, acquires a token, commits the sourced loan, reopens,
replays/retries the original CID without another effect, and checks public501
and readinessfalse. It does not substitute a successful mock callback.

Pure file/hash review verified the original RED raw checksum and its6 source
checksums against fbfb, then the three-test PASS raw checksum and its7 source
checksums against060022c and current files. These are author runtime results,
not an independent rerun. The manifests record a python3 command but do not
self-report the actual interpreter version; this review does not independently
attest the author's Python3.12 statement. No retained database was opened.

This review performed0 SQL,0 product imports and0 implementation/raw edits.
Only this separate report and evidence were added in the independent F01
worktree. No full matrix, package, production or activation approval follows;
the overall draft remains NO_GO.
