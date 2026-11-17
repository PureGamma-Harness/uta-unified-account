# Independent F02 acceptance: MAIN verifier identity accepted

The independent group accepts only MAIN verifier identity and the original
managed/path boundaries for candidate
`e7ca619b219812f9377ec98cf0a98caacca0da61`, implementation
`5924336a94688fccd5bd55c29a0b428914591f52`. Root integration review and
final full-source release gates remain required. Production approval is false.

Root authorized exact independent preregistration
`d9495b407e69feffa81d00f974a120deae6e06ab`. One fresh mode0700 scratch
component ran on CPU4/Python3.12.14/SQLite3.53.1 at
2026-11-17T16:15:06.354798Z to16:15:06.734156Z. The outer observer measured
0.379384336 seconds through the driver's END write and process return;
worker0.216566617 seconds, unittest0.187 seconds. All14 independent tests
passed with zero failures, errors or skips. No retries, timeout or forced
cleanup occurred. Source52 and the exact test/driver hashes stayed unchanged.
CPU4 was immediately released. Driver PID/PGID/SID247114 and worker247126
were reaped and their own `/proc` entries were later absent. The test worker
spawns no processes; no other process was inspected or signalled.

Both strong corruption cases were independently built from a genuine good
MAIN snapshot with different synthetic event IDs and balances. After copying
all five tables into TEMP in one real transaction, a restored-trigger MAIN
hash corruption and a MAIN balance corruption each received the same exact
original LedgerError through default and raw joined verification. MAIN and
TEMP stayed unchanged, query_only stayed1, and the caller transaction stayed
active. The F01 missing-event-FK/orphan99 fixture also remained refused by
default verification, the existing constructor and the joined verifier without
logical repair.

Healthy MAIN returned2 even when all five TEMP objects were views with wrong
column names. For every observed raw joined verifier call, a real SQLite
authorizer denied all TEMP READs; no denial occurred and every actual recorded
READ named main. The verifier trace contained no DDL, DML or transaction-control
statement. An uncommitted caller marker survived verification and disappeared
only after the test caller's rollback. Supported SQLite backup reopening also
returned2.

The real managed bound constructor and native read-role verifier passed without
replacing their native authorizers. Calling the two read-only schema helpers
directly on a raw managed connection still granted no join authority:
`unguarded_connection` remained the exact rejection. A subsequent unbound post
was `writer_fenced` and left base financial rows unchanged. A different actual
MAIN path retained its original StorageError. MAIN FK failure still preceded
version/hash errors; version preceded hash/balance, scales preceded hash, and
the original missing-trigger error preceded hash corruption.

The read-method-alias protocol retained the exact original checker function
bindings and rejected bad MAIN despite good TEMP. This is explicitly a protocol
control in the52-source tree, not actual M3 integration. The direct PR19 alias
review is separately sealed atcf96b6f. F02 adds no new method interface, but
M3's final combined-source runtime, loaded-code identity and package still need
their own gates.

The [manifest](../evidence/reviews/ledger-main-acceptance/once/manifest.json)
binds29 byte-identical safe copies and16 retained private database hashes.
Only the five base tables' rows and schema definitions were published; no DB
binary or owner/token row entered Git. All four original F02 databases, the
F01 original counterexample and all30 author fixture databases retained their
exact earlier hashes. Separate file-only review also verified all15 original
and36 fixed author safe/raw copies, both original source52 identities and the
author's fixed source52 maps. The original four false certificates remain
preserved; none was rerun or rewritten.

No runtime source was changed by this group. Acceptance does not extend to
other ledger methods, arbitrary raw-caller provenance, custom row factories or
Database subclasses, all partial catalogues, or the ordered API. No migration,
deployment, full QA/CI/package, production, HA, capacity or real-funds approval
follows. The following sealed NOT_RUN preregistration is retained as historical
context, superseded by these actual observations only within the stated scope.

## Original preregistration

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
