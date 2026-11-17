# F02 MAIN verification identity: preregistration, NOT_RUN

This is a stronger, separately authorized observation proposal. F01 remains
unchanged: its canonical postings-table definition fix and original catalogue
counterexample/raw database are not modified here. No additional SQL has run.

The earlier TEMP-only observation showed that a good MAIN database plus an
extra TEMP posting can still return2. That alone does not show incorrect MAIN
data being certified. The proposed cases instead establish actual corruption
of MAIN and retain valid TEMP data copied from a genuine earlier MAIN snapshot.

## Sources and manual data

Use two separate Python processes and source identities:

- Original verifier: immutable `/workspace/uta-observer-freeze-91e4ae4`, actual
  commit `91e4ae40b5e9b884c54026406299df5000c9c100`. All52 financial source
  bytes must also match original F01 baseline `4ad58b2169b02f8982a1cbef8722b79d705d60c8`.
- F01 candidate: this new F02 preparation worktree, whose52 financial source
  bytes must match tested F01 candidate `8003ef6c3e0cf98b4891efea7885ffa141a68fdc`.
  Its actual preparation HEAD is recorded separately, never relabeled8003.

Public Database/DurableLedger constructors and posts create two real events:
1250 USD minor units a-to-b, then300 b-to-c. The separately fixed literal
balances are a=-1250, b=950, c=300, and the original two event hashes must
match the precomputed manual reference from F01. No expected value is provided
by production replay/hash functions.

For each source, use separate fresh DBs for two cases:

1. `event_hash`: change MAIN event1's event_hash to64 `f` characters after
   temporarily dropping its original immutable-update trigger in an offline
   synthetic fixture transaction. Restore the exact original trigger before
   any verification. All MAIN catalogue definitions remain canonical.
2. `balance`: change MAIN b/USD materialized units from950 to951 in the
   offline fixture transaction. Journal rows and all original triggers remain.

Before either corruption, open a separate raw unmanaged connection to the same
MAIN path and create five TEMP tables by `CREATE TEMP TABLE name AS SELECT *
FROM main.name`. Thus TEMP rows originate from the actual good MAIN state,
not invented source rows. The script records complete genuine MAIN/TEMP
snapshots, then closes the offline corruption connection after its COMMIT.
The raw connection has no active MAIN transaction during this mutation.

First call the unmodified public object's standalone `verify()` and retain its
actual rejection: event-hash changed or materialized balances differ. This
proves that the MAIN corruption is real and detectable without TEMP shadowing.
Then set query_only on the raw connection, begin its real transaction and call
the exact original `verify(connection=raw)` against the same MAIN file. Record
the original result/exception, active transaction state and complete MAIN/TEMP
before/after snapshots, then roll back only this caller-owned read transaction.
If joined verify returns2 while unchanged MAIN remains bad and TEMP remains the
old good copy, record the stronger false-certification gap as reproduced.
Otherwise record the original refusal/non-reproduction without rewriting it.

## Proposed bounded run

One explicit `--run NEW_PRIVATE_OUTPUT`, Python3.12/CPU4, two source processes,
two cases each, four new private unmanaged SQLite files. Whole elapsed time,
including source guards/import/setup/output/cleanup, must be<=15s. A6s alarm
and parent wait bound apply to each own worker; technical failure stops the
remaining observation and retains NO_GO/partial evidence. The external root
launcher also enforces its whole budget. No retry or other SQL case is allowed.

Source52 maps, actual checkout identities, loaded storage.py paths/hashes,
source pre/post equality, original stdout/stderr and each full synthetic result
are retained separately. Both workers inherit the new component's process
group; timeout handling can terminate only its newly created workers. The
original F01/observer/credit databases, frozen source, clocks, old process
affinities and running experiments are untouched. No service or workload is
started. The root must approve exact committed driver bytes first.

## Proposed policy if reproduced: NOT IMPLEMENTED

`DurableLedger.verify` certifies the MAIN ledger selected by Database's original
path/transaction contract. Qualify all financial SELECTs with `main.` and both
integrity/FK pragmas with MAIN. Qualify `_verify_protection`'s catalogue read
with `main.sqlite_master`; F01's new postings-definition helper already does
so. Do not query TEMP's catalogue or add new native-authorizer permission.
Default and any experimental ordered-postings paths must share the same MAIN
identity, including metadata/group and payload queries after integration.

Raw unmanaged connection provenance remains its original caller contract;
managed registry/token/thread/fencing checks remain a separate layer. This
proposal neither grants permission to arbitrary raw connections nor certifies
all Database subclasses, other methods, attached schemas or all provenance.
No source is loaded from TEMP, and no original failure is repaired automatically.
If the gap is reproduced, implementation, independent review and new full
acceptance require their own exact source/hash and explicit next authorization.
