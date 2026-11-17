# Corrected-source managed baseline evidence

Frozen source: `7200097ce9f92fa678907bee9a99933f60d65bc3`.

**NO-GO for stability/production:** S1 contains one internal technical retry
(`bench:684`, attempts1, generic last_error), 418 financial responses over 1s,
and 113 locally full requests. Terminal safe rejection does not identify the
original internal exception. The original runner failed to detect this retry;
its actual source and manifest are preserved, with the oracle gap in analysis.

All 1,800 arrivals are retained. Mutually exclusive results: 1,169 financial
successes, 132 product rejections, 386 control/market rejections, 113 local full.
ACK1,687 and late418 overlap these outcomes. No unknown/QUARANTINED or lost
financial effects were found; independent RO reconciliation passed.

- `raw/`: original per-run files excluding authority databases, unchanged bytes;
  includes the preregistered plan and separate actual GO/execution manifest.
- `execution-driver.py` / `.log`: actual external recorder, including its
  incomplete pre-existing internal-retry stop gate; not a reusable launcher for
  arbitrary hosts with different cohost PIDs or source paths.
- `analysis.json`: counts, exact raw quantiles, original histogram bounds,
  latency segments, queue/feed data, profiles, cohost samples and explicit retry.
- `independent-review.json`: independent raw/SQLite verification without UTA
  imports, including the internal retry which the runner missed.
- `artifact-manifest.json`: full public artifact byte hashes. No DB is included.

Read [the report](../../../docs/managed-corrected-baseline-20261117.md) for the
business/technical limitations and actual hardware. B/P/S are separate short
probes; no throughput percentage is compared with the unsafe7a old probe.

Actual per-run commands are in `raw/execution-manifest.json`. Reproduction uses
`python benchmarks/run_managed_benchmark.py --output <new-private-directory>
--duration 10 --rate 20 --accounts 100 --shards 2 --cpu-limit 2`; P1 adds
`--profile`, S1 changes rate to100. Further load waits for new instrumentation,
source qualification and explicit GO. All successful orders stay OPEN; no
matching capacity or 24h continuity is claimed.
