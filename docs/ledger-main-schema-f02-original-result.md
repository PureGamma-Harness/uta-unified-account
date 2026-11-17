# F02 MAIN corruption hidden by TEMP: four original cases reproduced

**4/4 REPRODUCED, no fix applied to these observations.** This is a stronger
boundary result than a TEMP-only orphan with a good MAIN database. The exact
driver source is `0d0ca6aee9cbd3c788f2492c27c83e638e33f59f`, driver SHA256
`7f147c8bfcbe7009a85cdedd209b05164a4069a0b4e167b4e58767cdfd4c4bb1`.
The one approved CPU4/Python3.12 run lasted2026-11-17T15:44:52.906968Z to
15:44:54.184014Z, external1.277112654s. Two source workers exited normally,
no timeout, force or retry. Both complete52-source before/after guards match.
Bytecode writing was disabled only in these new processes; frozen sources and
original experiments were untouched.

| Source identity actually used | MAIN corruption | Standalone original verify | Raw joined original verify |
| --- | --- | --- | --- |
| Original immutable91e4,52 financial files also equal4ad58 | event1 hash changed | LedgerError: journal event hash changed | Returned2 |
| Original immutable91e4,52 financial files also equal4ad58 | b/USD950 to951 | LedgerError: materialized balances differ from journal replay | Returned2 |
| F01 candidate financial files equal8003, actual preparation HEAD0d0ca6a | event1 hash changed | LedgerError: journal event hash changed | Returned2 |
| F01 candidate financial files equal8003, actual preparation HEAD0d0ca6a | b/USD950 to951 | LedgerError: materialized balances differ from journal replay | Returned2 |

Every case began with real public constructors/posts and the fixed manual two-
event/four-posting hashes and balances. All five TEMP tables were populated by
CTAS from the actual healthy MAIN tables in one real raw BEGIN/COMMIT snapshot.
Only after that snapshot committed did another offline fixture connection
change MAIN. The event-hash case restored the exact original immutable-update
trigger before verification. MAIN catalogue definitions remained canonical.
The TEMP rows were neither hand-invented nor selected from the corrupted state.

Standalone verification first proved the MAIN corruption is real. The same
Database object's subsequent original `verify(connection=raw)` saw a real
caller-owned query_only transaction and the same MAIN path, but its unqualified
financial reads selected TEMP's old healthy rows. All four calls returned2.
Complete MAIN and TEMP snapshots remained unchanged, MAIN remained corrupted,
and the caller's transaction remained active. Both sources' actual checkout
identities, expected financial references and loaded storage paths are recorded
separately; preparation HEAD0d0ca6a is not mislabeled8003.

This is a verification-identity gap in the supported legacy unmanaged raw-join
contract. It does not establish a REST customer permission bypass, bypass a
managed actor registry or validate every raw-connection provenance boundary.
The F01 postings-catalogue repair still detects its narrow missing-FK case; it
does not by itself bind all later data reads to that same MAIN schema. These
results remain independent of F01's passing author/independent control batches.

The [raw manifest](../evidence/runs/ledger-main-schema-f02/original-once/manifest.json)
binds15 original file copies and four private DB hashes. All four MAIN databases
remain retained in the fresh private component directory; binaries are not
published. A separately timestamped metadata scan found no new component PGID/
SID residual, and the original F01 counterexample file hash is unchanged.
The postscan is not backdated into the component's original elapsed time.

Root has separately authorized only a minimal MAIN-qualified code proposal:
all verifier financial SELECTs, integrity/FK pragmas and protection catalogue
read name MAIN explicitly. No TEMP catalogue query or new native-authorizer
permission is needed. New fixed-code tests, independent review and complete
source acceptance are separate future evidence. There is no data repair,
migration, deployment, production, capacity, HA or real-funds approval here.
