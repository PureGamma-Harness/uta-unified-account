# Independent F02 MAIN acceptance preregistration: NOT_RUN

This separate tree starts from author evidence
`e44a8fc25a473f007578360181ef0eefa856352c`. Its runtime candidate is
`e7ca619b219812f9377ec98cf0a98caacca0da61`, implementation
`5924336a94688fccd5bd55c29a0b428914591f52`, storage SHA256
`8b4ba2f95c73fd288aef8bd20d8fbb166cd540ab3e9f0bebb0ef8afe9111d88c`.
The independent tree adds only tests, evidence and review text. F01, all
original F02 counterexamples, author code, databases and raw logs stay intact.

The proposed contract is that `verify` certifies MAIN. Genuine healthy TEMP
copies must not hide bad MAIN hashes/balances, and malformed TEMP data or
definitions must not change a healthy MAIN verdict. A real raw SQLite
authorizer will deny every TEMP READ during each joined verification. Actual
READ database identities must all be main, with no denied action. Both logical
states, query_only and the caller-owned active transaction must be preserved.

Fourteen independent controls cover the two original strong counterexamples;
healthy MAIN plus five TEMP views with wrong column names; the F01 missing
event FK with original postings/guards plus orphan99; main version, scale and
trigger error precedence; an uncommitted caller marker and later caller
rollback; a canonical real managed bound constructor/native read role; direct
read-only schema checks granting neither raw managed join nor write authority;
wrong MAIN path refusal; a read-method-alias protocol; a real supported SQLite
backup; and MAIN FK-check priority over version/hash errors. Financial data is
synthetic. Serialized rows are restricted to the five base tables; no owner or
token rows or database binaries enter Git.

The read-method-alias control checks exact checker function bindings and calls
the full original verifier. It exercises the protocol used by PR19, not that
credit module's unavailable integration in this52-source tree. The separate
PR19 review is `cf96b6f92809359a21d4eab651f64ee4d82a8002`; actual M3/F02
combined-source testing remains required. This patch adds no new checker API.

Pure AST review must establish exactly eight SQL literal changes within
`DurableLedger.verify` and `_verify_protection`. Undoing only the main qualifiers
must recover the full F01 module AST. Math, normalization, hashing, error text,
transaction ownership, the F01 definition helper and other ledger methods must
remain identical. No TEMP catalogue read, schema repair or authorizer exception
is introduced. Native managed authorizers are never replaced by the test's raw
connection observer. Passing read-only helpers must never be treated as an
authorization capability.

The single proposed Python3.12 component uses only CPU4, new mode0700 scratch,
a13-second owned-worker alarm and14-second owned-child watchdog within a
15-second total budget. The observer will measure the full process through its
END write and return, then record actual outer start/end. All failures remain
without retries. Source52 and test/driver hashes are captured before/after.
Only a timeout can signal the newly created owned child process group; no
existing job, status, workload, service, affinity or original database is
changed. No native/SQL execution precedes root's exact commit/hash GO.

Acceptance is limited to MAIN verifier reads and the original managed/path
boundaries. Other ledger methods, arbitrary raw-connection provenance, custom
row factories/subclasses, full partial-catalogue closure and ordered-postings
integration remain outside this claim. Final full-source QA, supported-Python,
CI and package acceptance remain separate. Production approval is false.
