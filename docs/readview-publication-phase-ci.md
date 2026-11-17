# Managed read publication-phase CI investigation

Investigated PR14 head: `4e59084544b8816e6e50e4caea7c6f60cff43a00`.
The supplied PR run `44049410166` failed one Python 3.11 test while its other
three jobs passed; the supplied push run `44049229592` passed its four jobs.
The failing artifact records the actual PR merge commit
`1702398f52970ac7b29619c46ad11b2a9f6909c2`, not the PR head SHA.
That merge object was unavailable in the local repository. Every file hash in
the artifact's complete validator input manifest was independently compared
with the investigated head and matched, including the test and both relevant
runtime modules. No later cache implementation is used for attribution.

## Original failure and evidence limits

The original ZIP is preserved unchanged at
[original-ci-artifact.zip](../evidence/runs/ci-4e-view-phase/original-ci-artifact.zip),
SHA-256 `a5d8348e692215ed95dead61e09d03e51136c97e2ccc049d5d83a6da508ad929`.
Its three members exactly matched the supplied summary, worker result and raw
unittest log. The raw log hash matches the summary:
`ec310773c639fcfd0fbc0a19ecff99194398dfd11479a4d5d6efaaceab2719cd`.

Python 3.11.18 / SQLite 3.46.1 ran 1168 tests, with one failure, no errors and no
skips. At test line 508, immediately after a timed-out partial publication, the
test expected `fresh_as_of_read` but received `missing`. The exact failure is
preserved in [the excerpt](../evidence/runs/ci-4e-view-phase/original-ci-failure-excerpt.txt).
The original test SHA-256 is
`42d5f46629dec1ef70766ffcb272f3b41e98e0b1e9c8851d5a391e99f3a14cfb`.

The original run did not retain the publication's per-shard receipts, full HTTP
body or database rows at this assertion. A shard-1 `startup_cancelled` traceback
appears after the FAIL line, when test cleanup can stop initialization; that
ordering does not uniquely establish what delayed shard 0. The original CI's
specific scheduling sequence cannot be reconstructed from these artifacts.

## Contract and actual phase reproduction

`start()` registers/spawns workers and starts the supervisor; it does not wait for
every worker's READY report. `publish_market(timeout=.25)` enqueues stable control
command IDs, waits within its receipt budget, then returns receipts and observed
watermarks. `publishing=true` means fanout is incomplete. It does **not** prove
shard 0 has already committed, even when shard 1 is intentionally held.

The account view labels an absent `uta_market` row `missing`; only the stored
snapshot can yield `fresh_as_of_read`. This behavior is correct and unchanged.

A small real loopback HTTP probe ran on the exact investigated head before the
fixture patch. Two real workers and a real managed database inherited one CPU.
The existing shard-1 hold remained five seconds. A separate legitimate shard-0
lease temporarily delayed its initialization; no financial function, HTTP
response, market value, clock or receipt was mocked. The initial phase was
observed at original quote age **0.370 seconds**, beyond the `.25` publication
wait and below the unchanged two-second freshness limit.

| Observed phase | Original command facts / database | Actual HTTP result |
| --- | --- | --- |
| Partial before shard-0 initialization | Both original CIDs PENDING; watermarks empty; shard-0 market absent | `missing`; financial readiness false |
| Release only shard 0 | Its original CID SUCCEEDED; exact original payload stored; same publication has only watermark 0; shard 1 PENDING | `fresh_as_of_read`, original version 1/time/digest; global HALTED/partial |
| Release shard 1 | Both original CIDs SUCCEEDED, complete original publication and explicit activation | Version 1 fresh; financial readiness true |
| Original timestamp naturally exceeds two seconds | Stored payload and version unchanged; workers alive | `stale`; financial readiness false |
| Publish a genuine new tick | Real version 2 publication/activation | Version 2 fresh and ready |

The [full phase JSONL](../evidence/runs/ci-4e-view-phase/baseline-phase-probe.jsonl)
retains returned publication/control/health/account fields plus per-shard market
payloads and original command results. The [exact probe source](../evidence/runs/ci-4e-view-phase/baseline-phase-probe.py)
retains its isolated worktree path; adjust `ROOT` when reproducing elsewhere.
These observations prove the faulty immediate-phase assumption is reachable,
not that this controlled lease schedule uniquely caused the original CI failure.
Separately queried HTTP, control and database observations are not advertised as
one cross-database atomic snapshot.

## Fixture-only correction

The original partial/stale/recovery case now:

1. Observes shard 0's real READY owner, matching PID and active lease, within a
   two-second setup budget **before** taking a fresh market snapshot.
2. Keeps the publication timeout at `.25`, requires `publishing=true`, then
   queries the original shard-0 PUBLISH_MARKET CID with a one-second bound.
   Only actual `SUCCEEDED` permits the strict local-view assertions to proceed.
3. Requires the original version, observed_at, digest and archive ID to match
   both the real HTTP view and stored market bytes. Missing, stale, future,
   terminal rejection, quarantine or timeout cannot pass this gate.
4. Confirms shard 1 is still PENDING and global control remains HALTED/publishing.
   The existing local-halt, unsupported-risk, natural-expiration, live-worker and
   genuine-new-version recovery assertions remain intact.

Deadline failures preserve the original CID, complete last receipt, original
publication and current control/per-shard market/queue facts in the assertion
message. `UTA_READVIEW_PHASE_EVIDENCE` optionally retains successful stages in a
new external evidence directory. No financial tables are changed by observation.

A new real-process control explicitly holds both owners, verifies the truthful
missing/PENDING phase, releases shard 0 and waits for that original command,
checks a retry uses the same publication IDs and remains partial, then releases
shard 1 and completes the **same timestamped** snapshot. It does not weaken the
original test's required fresh phase or count missing as a successful fresh read.

There are no runtime, TTL, lease-duration, market-age, startup-policy, queue or
financial-rule changes. Earlier successful/failed CI outcomes and the old
failure artifact are not rewritten. Existing producer `763`, historical soak
jobs and observers were not accessed or modified.

## Focused local result

```sh
UTA_READVIEW_PHASE_EVIDENCE=/tmp/new-empty-readview-evidence \
python3.12 -m unittest \
  tests.test_managed_views_reference.ManagedRouterReadReferenceTests -v
```

The three actual HTTP/process cases passed on Python 3.12.14 / SQLite 3.53.1 in
**6.134 seconds**, with one inherited CPU. The [raw result](../evidence/runs/ci-4e-view-phase/patched-http-py312.txt),
[stage records](../evidence/runs/ci-4e-view-phase/patched-phases/) and
[manifest](../evidence/runs/ci-4e-view-phase/manifest.json) retain the exact evidence.
No local Python 3.11 interpreter was available; this is not a claim to have
reproduced the original CI host or completed its full suite. Independent patch
review and the new exact-commit CI validation remain required. No load or long
stability run was started, and this result grants no production approval.
