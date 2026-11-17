# Synthetic credit with actual UTC freshness

This new case uses real `datetime.now(timezone.utc)` and monotonic clocks with
synthetic prices. It does not change the original static fixture's clock or
rewrite its earlier evidence. After the real native installer/acquire, it
constructs distinct initialized token-bound services with the real UTC provider,
then publishes a fresh synthetic quote through the actual native metadata scope.

The case passed once on source2176bc0, CPU3/Python3.12, at
2026-11-17 15:00:11.243196–15:00:23.016342 UTC (11.773s process, one unittest
11.637s). Raw commands, hashes, both actual borrow observations and actual clock
report are in `evidence/runs/credit-v2-realtime-clock/attempt-01`.

Actual observations:

* A sourced FIFO loan0.4 committed using the fresh SID. The observed actual
  selection was15:00:15.131488, final check15:00:15.369389 and recording
  15:00:15.369403 UTC. All were between independently observed real wall times;
  physical COMMIT timestamp remained null.
* Actual partial REPAY0.1 committed principal0.3. The test then let the original
  five-second market-age limit expire in real elapsed wall time, with no clock
  mutation. The next loan returned original-CID REJECTED503
  `market_unavailable`, with no intent and no loan effect.
* Publishing a genuinely different fresh SID through the native metadata scope
  restored new admission. Reusing the already-rejected stale CID still returned
  that same terminal rejection. A distinct explicit new command committed0.01,
  leaving principal0.31 under the new SID. The earlier dedicated loan replay
  still matched its original retained snapshot.

The operative real-clock segment took8.632s; this is a correctness test, not a
capacity or latency benchmark. Prices and funds are synthetic. This single case
does not establish live feed integrity, NTP/clock rollback handling, native
lease failover, process crash recovery, replication, production clock policy or
real-funds acceptance. Those remain separate gates. The earlier static-fixture
UTC values prove only actual calls to that synthetic provider, and remain
labelled accordingly.

V2 is still fresh-only, default off and not generally trading-ready. No HTTP/CLI
activation is added. Retain the exact compatible code/runtime and query original
CIDs after unknown outcomes; do not delete a capability or reuse an unresolved
static budget to roll back.
