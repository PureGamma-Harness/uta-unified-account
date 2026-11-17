# Independent acceptance: narrow main-catalogue fix accepted

The independent group accepts the minimal persistent-main postings catalogue
fix at exact `8003ef6c3e0cf98b4891efea7885ffa141a68fdc`, subject to root
integration review and combined-source gates. It rejects any broader claim
that effective TEMP tables, all raw joins, all five base catalogues or partial
catalogue repair behavior have been closed. Production approval remains false.

Root authorized preregistration
`66c345b2a4739055d9cb4d9954fde47966973eb5` without changing its tests or
driver. One fresh-scratch CPU4/Python3.12.14/SQLite3.53.1 component ran
2026-11-17T15:29:16.793718Z to15:29:17.425224Z. The outer observer measured
0.631523342 seconds through the driver END write and process return; the
worker took0.348310007 seconds and unittest0.312 seconds. All18 tests completed
with zero failures, errors or skips:17 positive/negative acceptance controls
and one deliberately separate known-gap observation. No retry or watchdog
occurred. All52 source hashes stayed unchanged. CPU4 was released. The worker
was reaped and its own `/proc` entry was later absent; the outer observer
reaped the returned driver. No other process was inspected or signalled.

The original missing-event-FK plus orphan99 fixture was independently rebuilt
in new private scratch. Both the retained-object verifier and existing
constructor rejected it. Every independently selected FK/PK/column/CHECK/view/
missing-table defect also received the intended typed error. Complete main
logical states stayed unchanged. Constructor traces contained no DDL or DML
before refusal. A failed joined verification retained its caller's active
transaction and marker; a successful joined post/verification was undone by
the caller's rollback. A real `uta.ops.backup_database` backup reopened and
verified the same two events. Real managed guards accepted a bound token and
read-role verification while rejecting an unmanaged raw join at its original
native boundary.

Equivalent whitespace DDL with matching PRAGMA columns/FKs was refused, as the
strict canonical contract requires. Constructor version99 errors still precede
catalogue errors. Verification deliberately prioritizes the new catalogue
error; malformed FK targets and missing native triggers do not displace it.

The TEMP observation **did reproduce**: a canonical main ledger plus a raw
unmanaged connection's TEMP postings table with5 rows, no FK/PK and orphan99
still returned2 verified events. A malformed main table hidden by a canonical
TEMP table was correctly refused. The former does not bypass the narrow main
definition check, and unchanged unqualified replay SQL shows that this raw-join
boundary predates the patch. Only the current source was executed natively for
this TEMP observation; no baseline native run is claimed. Separate baseline
and candidate source snapshots, exact executed fixture SQL, asserted counts,
and byte-identical retained main-file evidence are preserved in the
[boundary analysis](../evidence/reviews/ledger-catalogue-acceptance/temp-boundary-analysis.json).
The ephemeral TEMP connection was closed; no later query or reconstructed
raw TEMP dump is presented as an actual observation. Any patch refusing TEMP
shadows needs a separately authorized scope and regression contract.

The [manifest](../evidence/reviews/ledger-catalogue-acceptance/once/manifest.json)
binds29 byte-identical safe copies of this independent run, with19 private
database hashes including the supported backup. No database binary or
control-owner/token row is published. The original counterexample SHA256
remained `d77b0f8cc1797ac9376d10574927e609e1e93abf9b081bddeb5632639f87bb8a`.
Author evidence was separately read-only verified: all24 safe copies matched
the original raw bytes and source52 matched this candidate. A second static
peer found no narrow-scope blocker. The raw independent files remain at
`/tmp/uta-ledger-catalogue-independent-66c345b-once-20261117` without edits.

No runtime source was changed by this group. No financial migration,
deployment, HA, capacity or real-funds approval follows. The following original
preregistration remains as historical context; its NOT_RUN status was true
when sealed at66c345b and is superseded only by the actual records above.

## Original preregistration

The independent worktree starts from exact candidate
`8003ef6c3e0cf98b4891efea7885ffa141a68fdc`; runtime implementation is
`1ce3d6587b62be77120d3ef9914ec15c0b26c825` and `uta/storage.py` SHA256 is
`ddb6ed979bb8e88aefb2a49084829e9bdce3649fb10d6bf93bb0c28298f24a79`.
Author evidence is separately sealed at
`4c260d271ad8c49949f85544db50a2c30944057c`. No author source, raw file or
original counterexample is edited. This worktree adds only independent tests,
evidence and this review.

Pure source review confirms one helper and two call sites. The helper reads
`main.sqlite_master`, compares type, table name and the exact compiled SQL,
and performs no DDL. The existing constructor first preserves its original
unsupported-version refusal, then validates before its `_SCHEMA` loop. The
verifier checks the definition before integrity/FK checks. Removing the helper
and the two calls recovers the original whole-module AST. The seven original
trigger checks, hash/replay math and transaction code remain unchanged.

The planned single Python3.12 component pins only its own process to CPU4,
creates new mode0700 scratch, runs18 independent controls and retains all
failures without retries. Outer watchdog14 seconds and child alarm13 seconds
bound the whole component to15 seconds. The watchdog can signal only the newly
created owned child group; it does not inspect, signal, freeze or change any
existing job or workload. Source52 SHA maps are checked before/after. All
financial data is synthetic. Private fixture databases stay outside Git;
published state contains only the five base tables and schema definitions.

The matrix covers a real supported SQLite backup; exact metadata; the original
missing event FK plus orphan99; missing asset FK; invalid FK target; missing PK;
nullable account; generated column; missing CHECK; view and missing table;
equivalent whitespace DDL; constructor traces proving zero DDL/DML before
refusal; retained-object verification; joined-transaction failure preserving
the caller's transaction; caller rollback of a successful joined post/verify;
constructor version versus catalogue precedence; new catalogue versus old
trigger precedence; main/temp resolution; and real managed guards with a bound
token, read-role verification and refusal of unmanaged raw joins.

One explicit boundary observation is **not a closure claim**: static review
shows verification checks the main table definition but still reads unqualified
`ledger_postings`. A raw unmanaged joined connection can create a malformed
TEMP shadow with copied legitimate postings plus an extra orphan. Control17
records whether `verify` returns2 while the TEMP table has5 rows and no FK/PK.
The main authoritative catalogue remains canonical. This was already possible
before this patch; its relationship to the narrow persistent-main-schema fix
requires root review. The main-bad/temp-canonical control must refuse. No broad
claim about effective TEMP catalogues, arbitrary raw joins, other base-table
definitions or all partial-catalogue repairs is permitted.

Equivalent hand-reformatted SQL is deliberately rejected even if PRAGMA
metadata matches. Byte-preserving supported backups must remain accepted.
The constructor keeps version-error priority; verify intentionally gives the
new catalogue error priority over integrity, FK, version and trigger errors.
No automatic migration/repair, default-source integration, production, HA,
capacity or real-funds approval follows. Final acceptance remains pending
the actual run, preserved evidence, root review and combined-source gates.
