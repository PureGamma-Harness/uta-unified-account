# Final frozen managed smoke evidence

Historical scope note, added 2026-11-17: these are the final short observations
of the recorded `d73f4ed` workload, not validation of a repaired storage release.
They predate release-wide POSIX-close lock-ownership verification. Their original
reports and hashes are retained unchanged; no job was rerun for this note.
Long runs remain blocked until the complete release and every database override
passes independent locking regressions. Neither this short green nor the
original 887 job can satisfy that gate.

Candidate: `d73f4eddb1deef440afe5f50c9c9752b4a72f6d7`, based on `4c68f01`.
Runtime source, golden workload bytes and configuration were frozen throughout
each run. Every local step/round/fault checkpoint fact and its corresponding
hash-chain event now share one checkpoint transaction. Financial authority and
checkpoint commits remain explicitly separate; original financial IDs are queried
to recover the boundary. The earlier 81c smoke remains in the sibling directory.

| Case | Actual window | Rounds | Terminal account commands | Control commands | Matches / fills | Partial cancels | Risk decisions | Ledger events | Worker / parent SIGKILL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| smoke10 | 10.076 s | 3 | 18 | 6 | 6 / 12 | 3 | 24 | 21 | 3 / 1 |
| smoke60 | 60.108 s | 15 | 90 | 30 | 30 / 60 | 15 | 120 | 81 | 3 / 2 |

Both jobs completed with zero unresolved steps/faults, zero remaining debt, no
positions or order reserves, verified log coverage, successful integer/rational
cash/debt/pool/journal checks, all audit joins, and a subsequent cold read-only
audit. The collector also checked that every writer lease had been explicitly
released before exporting the financial snapshot. Actual native TLS/HMAC CLI and
independent worker PIDs were used; no signature, match or receipt was fabricated.
All data and initial capital/source references are synthetic. Private TLS keys,
signing profiles and the authentication database are excluded from the bundle.

No 6-hour or 24-hour run was started. Both duration flags, capacity qualification
and production approval remain false. This does not qualify earlier 887/observer
results, a different source version, external liquidity, HA or real funds.

Reproduce from the frozen source with distinct private directories:

```sh
python benchmarks/run_managed_soak.py run --directory /private/final-smoke10 \
  --duration 10 --worker-every 1 --parent-every 2
python benchmarks/run_managed_soak.py run --directory /private/final-smoke60 \
  --duration 60 --worker-every 5 --parent-every 7
python benchmarks/run_managed_soak.py audit --directory /private/final-smoke10
python benchmarks/run_managed_soak.py audit --directory /private/final-smoke60
```

Every case retains original job/progress/bootstrap manifests, bounded gzip event
segments, the cold audit result, a financial snapshot including schema/guard/
lease records and global pool claims, and a separate checkpoint snapshot.
`manifest.json` records hashes. The whitelist collector never exports private
material. The original source/configuration/environment hashes and actual counts
remain in raw files; recorded PID/start identities and canonical paths are
observations, not instructions for signaling another process or restoring files.

The focused tests passed under actual Python 3.12 (4 tests, 9.989s) and Python
3.10 (4 tests, 9.838s). Raw outputs are retained. The failure-injection test now
raises after both the local state-row and hash-event SQL writes, before their
shared checkpoint COMMIT: both roll back, then the original already committed
financial CID is recovered exactly once through the real CLI/TLS path.

Round latency includes the true CLI feed/activation, HTTP, queueing, worker
matching, fault recovery and checkpoint delay from scheduled arrival. The
60-second case reported P50 1645.633ms and P99/P99.9 2606.206ms; this is a paced
0.25-round/s golden scenario, **not** an open-loop throughput benchmark. Six
account commands, two real matches and control operations occur per round;
queued acknowledgments are never counted as financial acceptance. Co-hosted
hardware observations are in `host.json`; no resource-isolation claim is made.
