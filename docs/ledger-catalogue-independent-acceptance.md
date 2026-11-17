# Independent acceptance preregistration: NOT_RUN

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
