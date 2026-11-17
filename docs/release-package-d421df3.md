# Package acceptance: d421df3

The exact frozen source `d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6` passes a
fresh package exercise. Its sdist includes all 2753 tracked source/evidence
files with exact bytes. Its wheel and sdist contain the same dynamic 52
Python/HTML runtime files as the frozen source. A new environment actually
passes isolated installed CLI/protocol 8/8, all eight console commands and
installed read views 3/3. The no-`.git` sdist passes legacy 7, archived-profile
1 and release-verifier 19 tests without skips.

| Actual artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.5.0a1-py3-none-any.whl` | 279432 | `8fa7255d46075b8c14fc004994f219a9109569abedb50894f5678d603ac6abd1` |
| `uta_reference_exchange-0.5.0a1.tar.gz` | 30530638 | `61ad6c286bdaaf33f23d9fb65a22483419f6594f956cfc9b46b5552b7620e300` |

The runtime-tree SHA-256 is
`e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792`.
An actual Git-blob comparison confirms all 52 runtime files equal bb34's bytes;
all functional results above were executed anew for d421. The old bb34 full QA
remains **NO_GO**: its local Python 3.10 ERROR and two remote CI ERROR results
are retained. The test-only repair and its nine-case component checks do not
replace new complete candidate QA/CI.

Actual independent copies of the new wheel/sdist with one runtime file omitted
and eight separate sdist copies with each tracked historical CI ZIP omitted
all make the primary gate exit 1. A separate read-only checker requires all
seven report checks, the precise expected false set, exact artifact SHA/bytes,
the unchanged other positive artifact, and a member-by-member comparison
proving only the target was deleted. It includes stable member metadata and
contents. The earlier generic collector is unchanged; its broad boolean alone
is not accepted. Every ZIP is byte-identical in source, positive sdist and
unpacked source; original CI source hashes, merge identifiers and failures
are validated against their own historical reference commits.

[Raw logs, complete check matrix, safe allowlist and source hashes](../evidence/20261117-package-d421df3/README.md)
bind this result to the exact source and artifacts. The first independent
reporting attempt's tar-type JSON serialization error is retained. Correcting
that report-only serialization changed no archive, collector or source.
Only package scope passes here. This report grants no complete local QA/CI,
60-second matching/settlement/restart smoke, six-hour, capacity, HA, production
or real-funds qualification. Those gates remain separately owned and require
their actual results. `production_approved` is false.
Integration reports new d421 CI at six PASS and two failed jobs; the overall
candidate remains **NO_GO**, and the original CI evidence stays with that gate.

## Deployment and rollback

Keep frozen sources, original artifacts and old job directories immutable.
After the independent candidate gates permit a synthetic deployment, verify
both artifact hashes above and install the wheel offline into a fresh private
environment. Use new synthetic job/auth/TLS/observer directories; preserve
default settings unless a separate preregistered experiment selects otherwise.
Record the exact source, artifacts, process births and original deadlines.
Complete the offline capability, ownership, ledger, queue and audit checks
before publishing fresh market data and explicitly activating the new job.

On failure, close the new ingress, drain and stop only processes whose owned
birth identity matches. Preserve durable in-flight state and query original
command IDs before retrying. Never delete WAL, copy a live financial database,
reset generations or transplant an old job's observer state. Roll back a failed
synthetic deployment by starting a fresh environment from an independently
qualified prior artifact. An older writer must not open a capability-marked
database. A scheduling setting does not remove a persistent format capability.

This evidence commit itself changes only docs and safe reports/scripts; rolling
it back changes no runtime, balance, schema, process or original result. No live
deployment or financial activation was performed. The detailed existing
[observer recovery](milestone-observer-resource-recovery.md#deployment-and-rollback)
and [batch/credit](milestone-batch-credit.md#部署与回滚) contracts still apply.
