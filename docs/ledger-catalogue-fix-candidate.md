# Minimal postings catalogue candidate: author tests NOT_RUN

Implementation OWN1ce3d6587b62be77120d3ef9914ec15c0b26c825 adds one static
definition helper and exactly two calls: existing constructor after its version
refusal/before DDL, and default verify before foreign-key access. Removing the
helper and those calls yields the exact original whole `uta/storage.py` AST.
All original trigger, transaction, precision, posting, hashing and replay logic
is unchanged. The five-column postings table's compiled canonical definition
includes both exact foreign keys, PK order, NOT NULL, CHECK and no extra/hidden
column; a missing table or changed definition receives a LedgerError. Other
base tables and broad partial-repair closure remain out of scope.

Sixteen named controls implement the prior independent literal contract.
Negative fixtures perform offline reconstruction before either new verifier
path, preserve each resulting logical state across both refusals, and retain
case databases when the explicit task-specific output environment is supplied.
The valid control checks public construction/posting, joined verify, reopening
and a real canonical SQLite backup. The extension control uses real enable,
acquire and bound constructor/verify, then releases its original token; only
base-ledger rows and schema definitions are serialized, never control secrets.

The proposed single author batch is16 new controls plus13 existing
StorageTests, actual Python3.12, CPU4, new0700 scratch,14-second child alarm and
strict15-second external whole budget. `run_fix_controls.py --run NEW_OUTPUT`
has no default SQL action. Source52/hash guards, raw full unittest output and
per-control synthetic states are retained. Existing storage process-exit and
thread tests run only their new private authorities. No original DB/job, service,
registered pressure workload or old affinity is changed. Original catalogue
REPRO evidence/database remain untouched. Any error, timeout or short count is
retained and reported; there is no retry into green.

This source has only syntax/AST validation so far. Root must approve exact new
commit/driver before the one batch; another group must independently review the
code and raw results. No migration, deployment, production or capacity approval
follows. Canonical schema formatting is deliberately strict, consistent with
the original exact trigger contract. Alternate DDL support needs a separate
compatibility/version decision; automatic repair is forbidden.
