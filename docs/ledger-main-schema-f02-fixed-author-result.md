# MAIN-only verification fix: author component passed

Exact candidate `e7ca619b219812f9377ec98cf0a98caacca0da61`, implementation
`5924336a94688fccd5bd55c29a0b428914591f52`, completed one authorized author
batch on CPU4/Python3.12.14. Actual interval2026-11-17T15:57:28.114248Z to
15:57:29.646197Z: external1.531980346s, child1.399674s, unittest1.332s.
All41 tests passed, zero failures/errors/skips:12 new MAIN-identity controls,
16 original F01 catalogue controls and13 original StorageTests. No timeout,
forced cleanup, source change or repeat occurred; both52-source maps match.
Independent acceptance and full-source qualification remain pending.

The fixed tests retain the original expected errors for bad MAIN hashes and
balances despite genuine good TEMP copies. They additionally reject bad MAIN
postings, ledger version and asset scales. F01's malformed MAIN catalogue still
refuses. Healthy MAIN returns2 despite TEMP's bad hash, balance and orphan row;
TEMP is not the authority for this certificate. Both MAIN and TEMP states and
the caller-owned active transaction are unchanged across verification.

One real raw-connection authorizer denied every TEMP READ. Verification still
returned2 with no denied action, and every actual recorded SQLite READ named
database `main`. This tests the absence of a TEMP-read permission requirement;
it does not replace native managed guard validation. The separate genuine
managed read transaction succeeded, raw unregistered managed join retained its
original `unguarded_connection` refusal, and a different MAIN file retained
its original path refusal. The F01 matrix also retained canonical backup,
joined/fenced positive behavior and no-repair catalogue negatives.

The source change is eight SQL string qualifiers only, within verify and its
protection catalogue read. Undoing those qualifiers recovers the exact previous
whole module AST. Math, hashing, normalization, error messages, F01 helper,
caller transaction handling and other methods are unchanged. No TEMP catalogue
query, native-authorizer exception, automatic repair, schema or data migration
was added. Raw unmanaged caller provenance remains its existing contract;
row factories, arbitrary Database subclasses and other methods are not declared
fully solved by this change. The independent ordered-postings branch needs its
own MAIN qualification/integration tests before combination.

The [manifest](../evidence/runs/ledger-main-schema-f02/fixed-once/manifest.json)
binds36 byte-identical raw files and30 retained private database files across
28 new fixture directories. Serialized financial rows are restricted to the
five base-ledger tables; no owner/token rows or database binaries are published.
All four original F02 databases and the original F01 counterexample retain
their earlier exact file hashes. A separately timestamped postscan found no own
PGID/SID residual; it is not backdated into the original component duration.

No deployment or production approval follows. Another group must independently
review this candidate and its raw evidence, then the integrated exact source
must pass its complete release gates. Preserve refused authority state and all
original failures. Rollback must not overwrite journal history, relabel the
original false certificate or treat a narrow author result as full provenance,
capacity, HA or real-funds acceptance.
