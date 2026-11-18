# First E707 native SQLite matching result

Classification: **local functional PASS, pending independent RAW review**.
Source `e707fc55e83f53d79aa27610ea8f7b6386f6c713`, manifest SHA256
`2bfda9eed7530fdfd0f462648e86cbcb3bf546b1fc2c3971894338ce81d51b4c`,
plan SHA256 `c4e4604c6bbab13c5fb3799de8fc84e42d36b86b88c9ebf68576793e6237cc0c`.
Independent CODE review `895ca28f0e6a6a0e17ccf818756a8548d507b6e9` preceded
root's exact once authorization. This was one run; no case was retried or
rerun. Old source `fafd5959` remains NOT_RUN with zero attempts and its static
allowlist finding retained. The earlier pure result and materialization event
remain separate and unchanged.

Three fresh, configured Cross authorities committed **five unique matches and
ten paired fills**. Six matcher attempts included one MM rejection. Separately,
three planned direct-command rejections covered fresh fill MM equality, fresh
order MM equality and conflicting reuse of an existing fill ID. Accepted order
and fill IDs were replayed once each without further effects. The matcher
cancelled one rejected order; one remaining counterparty order was explicitly
cancelled through the native API. All final orders are terminal.

| Authority | Actual result |
| --- | --- |
| MM equality rollback | A/B's real ETH opening trade remains committed. A genuine ETH mark change makes the proposed BTC seller land exactly on MM. A direct fill rejects without effects. In the real BTC match, a bounded read-only profile observes B's provisional first leg returning before A's strict-MM rejection; the savepoint rolls back both settlement legs. Only A's documented cancellation remains. A new equality-boundary order also rejects without effects. |
| IM equality with lower MM | A real BTC match leaves A equity10, IM10, MM5 and availability0. The original reduce-only orders then close both positions through a second actual match. Final customer cash is A9.96/B999.92, with systemfees.16. |
| Cumulative partial fee, USD2 | Two distinct original counterparty orders produce actual .4/.6 partial matches. A's one order charges [.01,0]; B's separate orders charge [.01,.01]. Final A cash/equity.10, IM.10, MM.05, availability0; B9.98 and systemfees.03. This finite fee case supplies no throughput claim. |

All three authorities were reopened. Complete application table/schema
snapshots matched across reopen. Native ledger hash replay, strict matching
and independent cashflow/position/cumulative-fee reconciliation passed with
zero unpaired fills. Journal events were4/6/5 and postings8/12/10. Manual cash,
fees, custody, position quantities and signed costs matched. One original
actual FILL per authority also passed existing numerical decision replay.
That numerical replay does not test strict-MM admission eligibility,
historical ownership or freshness; the full admission replay model remains OPEN.

The actual timeout/taskset prefix exited0 and was reaped; the invoking exec
session returned0. Its Popen-to-wait interval was **3,796,115,108 ns**. The
separate driver result-stage duration was3.696681132s and the final END-stage
duration was3.758643664s. They are different measurement boundaries and are not
arrival-based latency or capacity measurements. There were154 checkpoints.
The result-stage observed size was4,857,651 bytes; the final END/inventory size
was4,893,058 bytes, below the64 MiB logical target bound. A kernel directory
quota, replication and blocked-I/O realtime guarantee were not proven.

Actual affinity was `[1]`, Python3.12.14, SQLite3.53.1, with the expected
interpreter SHA and `-I -S -B`. Builtin/extension metadata matched before any
database and after execution. All63 source pins and imported UTA origins
matched the frozen mini and original checkout. There were no forbidden imports;
the final Python thread count was1. This is not kernel-thread enumeration or
complete native-library attestation. No worker, network, auth or process probe
was run, and the native five-second freshness policy was retained.

The allowed original stdout is26,972 bytes, SHA256
`56a9f75499a0a65c6cef7397cb8b7b440e25b470a93ad3d895de14d8ab5c6f45`;
stderr is empty. The156 original JSONL records contain only the strict BEGIN,
checkpoint and END key sets and were copied unchanged after inspection.
The512 KiB shared raw bound retained its512-byte failure trailer; no timeout,
overflow or incomplete-write fault was injected.

Original databases, sidecars if present, full source capsule, full case reports
and the complete ZIP remain **LOCAL PRIVATE**. The sealed original set is80
files/4,939,245 bytes, with80 ZIP entries passing CRC checks. Public delivery
contains explicit financial/count/runtime projections, table/schema hashes,
byte inventories and the allowed raw streams. It exports no original database,
complete case report, capsule, actual nonce or private ZIP. File origins and
hashes are recorded in `export-manifest.json`; table hashes use sorted-key,
compact JSON of the captured rows and are distinct from ledger event hashes.

Perpetual funding remains unimplemented in this runtime; this run used the
real market-publication API. No funding payment or SQL cash change was
fabricated. Performance, HA, additional products, production and real-fund
activation remain unaccepted. No push, CI, extra load test or financial
execution followed this first run.
