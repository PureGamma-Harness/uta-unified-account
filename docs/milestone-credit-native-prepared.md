# M3 synthetic credit: native preparation and offline evidence components

This milestone implements an explicitly invoked, fresh-only **NATIVE_PREPARED**
capability. It grants no product, mode, order type or credit operation. It cannot
acquire a financial writer, become READY or activate. The list of supported
credit trading formats is empty. Existing authorities without the capability
keep their previous contracts, including new managed borrow returning 501.
No CLI flag or client borrowing route is introduced.

The complete latest M2 ancestor `8338bee` was merged before implementation;
existing financial code was not copied from an older checkout. The isolated M3
branch does not change the frozen M2 release or running test authorities.

## Delivered scope and review gates

| Component | Delivered behavior | Acceptance evidence and limits |
| --- | --- | --- |
| Static budget policy | Strict bounded canonical descriptor; explicit zero new interest/fee synthetic policy; complete ordered shard allocations, unique funding claims and sum of assigned limits at most global | Independent 108 semantic and 157 wire corpus, exact integer production differential; declarations are not proof of external funding or live global usage |
| Native prepared inventory | Persistent immutable capability/schema/archives, exact four base/batch/credit/both inventories, old actual binaries refuse unknown credit state, real UDF/authorizer always deny positive credit | Initial 14 cases, 122 compatibility cases, final native17+policy12 on Python3.10/3.12/3.13; no active trading format or successful credit operation |
| Source preflight | Original full ledger and credit verification in the same actual control write transaction, before opening claims and first native DDL | Independent actual old-source two-case RED COMMIT/reopen; new-source typed rejection/ROLLBACK/no native objects; healthy PREPARED only, 0.890334s |
| Code artifact | Actual deployed source, loaded functions/defaults/closures, fixed actual dependencies, module/class static constants and runtime identity; strict archive reader | Three original identity counterexamples retained and independently closed using original inputs; no archive imports/execution, no permission or complete credit replay |
| Offline borrow transition | Exact gross cash/principal/interest/pool/receivable changes, local static limits and four complete ordered legs; final version and untrusted public result contracts | Real synthetic preseal COMMIT/reopen control; final15 tests on three runtimes; independent 51-case integer/Fraction differential and original four safety assertions, supplied quotes remain inputs |

Independent reviews and original failures are retained with source and raw
hashes. These are software workgroup reviews; they are not human financial
signatures or production authorization. The entire new integrated branch has
not received a full release matrix, load acceptance or multi-node DR test.

Useful entry points:

- [Prepared capability, native rules and recovery](credit-native-prepared-runtime.md)
- [Independent actual source preflight](credit-native-source-independent-review.md)
- [Code identity and all development failures](credit-code-artifact.md)
- [Independent identity correction](credit-artifact-fc63938-independent-recheck.md)
- [Offline accounting and remaining proof boundary](credit-transition-arithmetic.md)
- [Independent static certificate corpus](managed-credit-m3-independent-test-plan.md)

## Deployment and rollback

No production deployment is part of this slice. An engineer may use a new private
synthetic database: complete its offline bootstrap and full reconciliation,
enable the existing writer fence without ever acquiring an owner, then call the
internal explicit preparation function with the reviewed immutable certificate.
The inbox must be unused and the exact fresh control-event prefix must match.
Prepare and owner acquisition serialize through the real database transaction;
only one can win. Existing or previously owned authorities are refused.

Preparation verifies the full existing financial source, local opening debt and
pool, and actual local immutable funding receipts. It installs all native
objects, table guards, policies, certificate, local allocations, opening legacy
receipt hashes and capability marker in one control COMMIT. Any failure leaves
none of those new objects. Repeating the same descriptor verifies the exact
inventory; conflicting or partial state is refused and never repaired silently.

After successful preparation the database remains closed to trading. An old
binary cannot downgrade it. Preserve the database and failure evidence for a
reviewed forward migration. Do not delete a marker, rewind generation, edit the
certificate, reassign UNKNOWN capacity or overwrite a database with an older
financial snapshot. Self-created disposable test databases can be cleaned up;
the tests do not authorize deletion of any other authority. Unwired arithmetic
and artifact code can be reverted before a future format depends on their
retained identities; retain matching builds once real decisions reference them.

## Blocking next implementation

There is no positive managed borrow path. Before defining a supported native
trading format, all of the following must be implemented and independently
verified together:

1. A complete content-addressed `CREDIT_BORROWED` decision and strict operation
   replay: actual market SID/payload, original quote and end-check times,
   gross pre/post account state and risk, catalog/rules/credit policy/code
   identities, actual local limits/budget use and pool/source evidence, complete
   sealed journal and version changes. Generic risk replay or matching code
   identity alone is insufficient.
2. An immutable first-source receipt and explicit borrower/funds authorization,
   HMAC replay protocol and durable FIFO dispatch. Reader/trader roles must not
   inherit borrowing. A retry queries the original CID and preserves its original
   business effect and first-source identity. Legacy credit receipts without an
   inbox need a defined compatibility policy, without fabricating success rows.
3. A positive native operation context bound to actual connection, process,
   fencing token, financial role, CID and staged database obligations, with
   authoritative expected postings, sealed closing point and terminal receipt.
   SAVEPOINT rollback, caught late financial errors and actual outer COMMIT
   failure/reopen must be proved. In-memory counters are not SQL obligations.
4. Explicit cross-shard UNKNOWN handling and immutable offline budget versions.
   No single-shard aggregate is an atomic global limit. Missing authority data
   never releases another shard's allocation or unknown debt.
5. Lending distress/liquidation integration, scheduled interest, real currency
   product validation, independent financial sign-off and real-funds activation
   approval. USDT/USDC, automatic borrowing, production throughput, replication,
   RPO/RTO and sustained capacity remain outside this milestone's acceptance.

The current default-disabled state remains the required outcome until these
gates pass. No synthetic reference loan, prepared database or arithmetic match
may be reported as a production loan or throughput success.
