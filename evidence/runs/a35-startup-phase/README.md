# Original inflight writer and keeper phase

The original a35 PR CI Python 3.12 result is retained byte-for-byte: 1243 tests,
one ERROR, actual merge 2959d4d. All 227 recorded test/fixture/code input hashes
match a35; its native keeper BEGIN raised database-is-locked and startup failed
closed. The failing fixture released its old writer, then immediately tried the
real keeper renewal. Release is not a COMMIT witness. This trace alone cannot
prove a unique historical scheduling cause.

A separate controlled comparison wraps the real old writer's final guard with
an actual 0.2 second wait and then calls the original function. Unchanged a35
fixture reproduces native BUSY and startup_keeper_failed; the changed positive
fixture succeeds with the same pause. Both original logs and the exact driver
remain. No financial result, lease, clock, keeper or original verification is
faked. This is a representative interleaving, not an attribution of the unique
CI stall or production timing/capacity evidence.

Only this positive ordering test now uses the existing normal five-second
lease and waits, within one second, for the original writer to return after
its actual transaction. Full original RO replay must then observe that one
committed journal. The test also verifies the old thread terminated. Its total
startup work budget stays three seconds; every other short-lease, lost-reply,
expiry and external-BUSY case stays unchanged. Runtime keeper's min(lease/12,
0.1) SQLite timeout, final fencing and unknown-renewal poison remain unchanged.
The separate actual external-writer BUSY test remains required and is included
in the focused follow-up suite.

There is no service/schema/data migration. Rollback restores this test fixture
for future checks while retaining original red evidence. It cannot authorize
production or reuse a35's failed CI as a pass. New combined fixed-source full
runtime/CI/package qualification remains mandatory before performance GO.
