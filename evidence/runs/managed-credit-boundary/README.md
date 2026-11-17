# Managed owner credit boundary

`red-manifest.json` pins the A1 runtime at `1c14441`, new test bytes and exact raw
red output. Both public and private paths actually COMMIT a new unaudited loan
before their two assertions fail; three controls pass. This is a trusted local
owner API finding, not an ordinary managed HTTP path.

The fixed extended runs execute **113 tests** on each of Python 3.12/3.10/3.13,
all passing with zero skips. `extended-runs.json` records actual commands,
timestamps, durations, parent commit, runtime hashes and log hashes. These are
targeted runs on exact recorded working bytes before their commit, not frozen
full-release qualification. The first 52-case core run and single real caller
savepoint case are retained separately rather than replacing their logs.

New cases preserve pre-seal borrowing and original-command replay and prove
existing-debt repayments still work when halted/stale. Existing durable repay
fixtures seed the same obligations before sealing; all original financial
assertions remain. The savepoint case shows a real post-ledger business error
and caller-owned rollback, not fictitious helper atomicity on caught errors.

No capacity workload, long run, production approval, schema migration or online
new-borrow protocol is supplied by this patch. All keys/funds/data are synthetic;
no historical live job or frozen candidate was modified.
