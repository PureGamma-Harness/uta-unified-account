# Proposed base-ledger catalogue validation: NOT IMPLEMENTED

The original observation establishes a missing event FK accepted by both the
reopened constructor and default verifier. Root has not authorized this fix or
its tests yet. This proposal is separate from default-off ordered-postings R&D;
neither path may claim that ignoring unmatched inventory preserves integrity.

## Minimal policy

Extend the existing `DurableLedger._verify_protection` catalogue validation to
require each of the five original base tables, in addition to its existing
seven exact trigger definitions. For every expected table require its exact
`sqlite_master` type, name and original compiled definition from `_SCHEMA` after
the same `IF NOT EXISTS` removal SQLite performs. This defines columns, types,
NOT NULL, CHECK, PK, UNIQUE and FK declarations, rather than believing only
`ledger_schema.version`. A view or a table missing a declaration refuses.
Retain the existing trigger checks and messages; add explicit LedgerError
messages for a missing base table or changed base table definition.

The current ledger already requires exact original trigger SQL, including
formatting. The proposed base-table policy deliberately supports the canonical
schema created by this code and byte-preserving SQLite backups/dumps. It does
not silently accept hand-reformatted or semantically altered DDL. A future
need to accept alternate canonical schema representations requires an explicit
compatibility/version contract and tests; it is not inferred by dropping tokens
or removing constraints. Full exact source definitions avoid another hand-
maintained partial PRAGMA inventory that could miss a CHECK or collation.

This validates only the fixed base inventory. Product tables and legitimate
fencing/audit extension triggers remain under their existing separate fixed
registries; this small change must not reject or bless them by a new prefix
heuristic. No unrelated table is dropped or repaired. Constructors must perform
the new check before any existing-schema CREATE IF NOT EXISTS statements, and
both default and opt-in verification paths must perform it before claiming
reconciliation. Automatic initialization of genuinely empty new files remains
the original path; a partial existing ledger refuses without repair.

## Required next controls, all NOT_RUN

- Original canonical public schema still constructs, posts, reopens, verifies
  and joins a real transaction without changes to balances or hashes.
- The retained original malformed case is never overwritten. A new independent
  fixture with the same missing event FK refuses in existing constructor and
  verifier. Calling verify on a retained object must also refuse after offline
  catalogue mutation; rejection cannot rely only on constructor behavior.
- The minimal event FK removal, asset FK removal, PK removal/change, column
  type/NOT NULL/CHECK drift, unexpected extra/hidden column and view substitution
  each refuse with the intended catalogue error and zero logical repair.
- A missing original table in a partial catalogue refuses before constructor
  DDL. Original missing/altered trigger controls preserve their old errors when
  base tables remain intact. Multi-fault precedence is documented.
- Both default and opt-in ordered-postings paths, if integrated, retain the
  same catalogue policy; original data-corruption messages remain unchanged
  for catalogues whose base schema is valid.
- Relevant ordinary ledger, transactional, restore, managed-fence, audit and
  M3 existing-service factory suites must be independently reviewed. The author
  cannot sign off their own fix; complete source qualification remains separate.

No ledger schema version or stored balance changes. Deploy only a newly
qualified code artifact; existing noncanonical catalogues fail closed and need
an independently authorized recovery/import process, not automatic DDL repair.
Rollback must not restore a false reconciliation claim or alter the original
failure. A prior artifact can be retained for forensic reproduction, with new
ingress closed for affected authorities. No production, capacity, HA or real-
funds approval is included.
