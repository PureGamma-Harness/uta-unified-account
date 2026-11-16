# Frozen managed TLS/HMAC smoke evidence

These are separate synthetic managed-process smoke jobs on candidate
`81c7e5b7e9965723854b7bcc2b8966b9d3d0b8ae`, based on `4c68f01`.
They do not qualify the earlier 887/observer run, 6/24-hour stability, capacity,
HA or real funds. All corresponding flags remain false.

| Case | Actual window | Rounds | Account terminal successes | Real matches / fills | Partial cancels | Required risk decisions | Worker / parent SIGKILL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| smoke10 | 10.165 s | 3 | 18 | 6 / 12 | 3 | 24 | 3 / 1 |
| smoke60 | 60.151 s | 15 | 90 | 30 / 60 | 15 | 120 | 3 / 2 |

Controls are separately counted: 6 and 30 committed market/activation commands.
Journal counts are 21 and 81, including six explicit bootstrap events. The
initial loans of 6 and 30 BTC satoshi were fully repaid. Every account command,
actual trade/order/fill, per-currency posting/projection, gross debt, pool cash,
market digest and required audit join passed the independent integer/rational
oracle. Fresh feed uses actual UTC with monotonically increasing versions; it
is synthetic constant-price input, not an external market calibration.

Both jobs used the actual `uta.durable_cli serve`, native verified TLS 1.2+,
real HMAC with per-attempt nonces, one process shard and three fixed accounts.
The outer runner never wrote managed finance or fabricated execution. Runtime
private keys, signing profiles and the nonce database are deliberately excluded
from this public bundle. All included account and funding records are synthetic.

Reproduction from a clean checkout (each directory must be new and private):

```sh
python benchmarks/run_managed_soak.py run --directory /private/smoke10 \
  --duration 10 --worker-every 1 --parent-every 2
python benchmarks/run_managed_soak.py run --directory /private/smoke60 \
  --duration 60 --worker-every 5 --parent-every 7
python benchmarks/run_managed_soak.py audit --directory /private/smoke10
python benchmarks/run_managed_soak.py audit --directory /private/smoke60
```

Each case contains the original job/progress/bootstrap plan, hash-chained event
segments and manifest, a new cold read-only audit, and a compressed whitelist
export of the actual financial tables plus global pool-source claims. The
collection script never exports authentication/key material. Case checksums are
in `manifest.json`. Runtime paths and PID/start-time identities in the raw
synthetic evidence are observations of the original jobs, not reusable process
identifiers or portable backup instructions.

Latency is round completion from original scheduled arrival, including CLI
publication/activation, TLS/HMAC, queueing, real matching, and process recovery.
It is not admission latency or an open-loop throughput measurement. These
co-hosted jobs have no resource-isolation claim. The 60-second case reported
P50 1576 ms and P99/P99.9 2420 ms; the 10-second case reported P50 2406 ms and
P99/P99.9 2425 ms. Exact values and environment/source/configuration hashes remain
in each raw progress/job manifest.

The focused tests cover actual TLS and both faults, financial COMMIT/checkpoint
failure recovery under the original CID, historical partial-fill recovery,
independent money/count checks, log corruption detection, and refusal to start a
long job without its explicit frozen-source opt-in. Raw outputs for Python 3.10
and 3.12 are retained beside this file. No 6-hour or 24-hour job was launched.

## Retained earlier candidate

This initial `81c7e5b` result is retained unchanged. A subsequent local-checkpoint
review found that state rows and their corresponding log events used separate
checkpoint transactions. Financial original-ID recovery already passed, but that
local audit gap was then closed in `d73f4ed`. The final smoke bundle is
`../20261116-managed-smoke-final`; this earlier result does not validate the
new atomic checkpoint/event contract.
