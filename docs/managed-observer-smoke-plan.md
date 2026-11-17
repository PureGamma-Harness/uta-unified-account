# Pending one-minute observer smoke

Status: **prepared, not started; awaiting the new final freeze, complete QA and
root GO**. This plan creates no service, listener, worker, job or long observer.
No 4608 single-runtime success is substituted for an overall release decision.
All six-hour/24-hour/production/10k flags stay false.

The selected producer freeze is now
`/workspace/uta-operations-freeze-7ae94eb` at
`7ae94eb8a783f8e134ac90c11a713df7bb02d5f1`. Root's three-runtime full QA is
pending beneath `/workspace/uta-operations-validation/7ae94eb`. Smoke waits for
the complete overall decision and the exact matching Python 3.12 report/runtime
paths from root. This document does not mark those ongoing checks passed.

Before GO, finish the independent boundary review, commit the observer fixes and
run only private tiny SQLite/process-identity/namespace tests on one CPU. Root
selects the new producer freeze/SHA, its genuine complete validation `summary`
with sidecars and the matching Python/SQLite runtime. The observer checks these
exact inputs; no synthetic report, allow-dirty path or eligibility bypass is used.

After GO, create a fresh owned `0700` scratch root outside every source checkout
and previous job, with separate `job/`, `observer/` and launcher-private logs.
Use `Popen` PIPEs, not inherited regular-file standard descriptors. The launcher
alone saves allowlisted/redacted output to this scratch root. Inherit one allowed
CPU for producer, workers and observer; do not change affinity of any other PID.
Record the actual driver PID and birth ticks immediately at launch, without
reading command lines, environments or other jobs' proc data.

The producer command, with values supplied only after root GO, is:

```text
EXACT_QA_PYTHON -B benchmarks/run_managed_soak.py run
  --directory NEW_PRIVATE_SCRATCH/job --duration 60
  --worker-every 5 --parent-every 10
  --validation-report NEW_EXACT_QA/summary.json
```

It executes the existing real synthetic required-audit TLS/HMAC workload:
15 planned rounds at 0.25 rounds/s, three fixed accounts, no load-rate changes,
worker recovery every five rounds and one parent recovery at round ten. There
is no six-hour or capacity run. Its source is the selected clean frozen producer
checkout; observer code stays in the separate frozen observer checkout.

Take bounded independent observer CLI samples during startup, an actual ACTIVE
round/fault recovery and after the driver exits. If a read bracket straddles
progress, its expected result is inflight/unknown. Capture the actual 60-second
watch cadence where timing permits; no catch-up loop or faster load generator
is introduced. Kernel RO mounts must leave host PID/stat identities visible,
deny pathname writes and protect SQLite sidecar races. Missing validation,
unknown process visibility or unavailable live sidecars must fail closed.

Acceptance for this **smoke only** requires the actual producer to finish all
15 rounds with verified final logs, observer PID births/generations and raw
financial facts to agree, original start/deadline/source hashes to remain pinned,
no ACTIVE/unknown state to become final PASS, and independent final integer/FK/
watermark reconciliation to pass. The observer must still report
`final_evidence_eligible=false` because 21,600 seconds/5,400 rounds were not run.
The public `producer-audit` six-hour gate must reject this short job. If an
additional engineering-only producer cold audit is requested, execute it against
a bounded private complete clone with exact validation sidecars; label it short
smoke evidence and never issue a six-hour producer receipt or signoff.

The launcher wall-clock budget is at most 150 seconds including initialization,
60 active seconds and cold checks. On timeout, preserve private evidence and
stop only this scratch job's recorded PID/birth identities. Never signal or
inspect PIDs 4471/8784, never read/change the earlier 887 source or databases,
and never reset a failed job to manufacture success. Publish only a small
allowlisted redacted summary; never recursively archive TLS/auth files or private
complete clones. Reserve clone/output disk and address-space budgets beforehand.

## Execution-target addendum: 763202d

This addendum supersedes the execution target only; the 7ae94eb preregistration
above is retained unchanged. The actual target is
`763202df9cb3ce089721e5281371aff3eab58089` in
`/workspace/uta-operations-freeze-763202d`. The genuine matching Python 3.12
report is `/workspace/uta-operations-validation/763202d/python312/summary.json`,
with 1,110 tests and SHA-256
`5cf2d73afddbd0cd0da41e895ac46d61368f31d7f0f174741566660fb42e3201`.
Its actual validator command selected
`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`.
The prepare invocation read those real fields; it did not fabricate an
all-passed report or create a job.

Root subsequently confirmed all three local runtime reports, CI and fresh
package checks passed and issued **GO ONLY for one actual isolated 60-second
smoke**. There is no six-hour authorization. No actual start/end time or result
is filled in by this plan; those are recorded only when execution occurs.

The separately prepared `tools/managed_observer_smoke.py` defaults to `prepare`.
It keeps the frozen observer's main/finance bytes at f6f7167 unchanged and uses
trusted PIPE capture with bounded stdout, unknown-key filtering, stderr hashes,
actual PID/birth and measured launch/end timestamps. Only its explicit
`produce-60` operation starts the real producer, with the exact report-selected
Python, duration 60, worker-every 5 and parent-every 10. All child processes
inherit one allowed CPU. Every output remains in a new owned `0700` scratch root.

For the selected fresh scratch root
`/workspace/uta-managed-observer-runs/763202d-smoke-20261117`, the exact sequence
from the separately frozen observer checkout is:

```text
python -B tools/managed_observer_smoke.py produce-60
  --job SCRATCH/job --output SCRATCH/observer --record producer-response.json

python -B tools/managed_observer_smoke.py observe-once
  --job SCRATCH/job --output SCRATCH/observer --record live-01.json

python -B tools/managed_observer_smoke.py observe-once
  --job SCRATCH/job --output SCRATCH/observer --record final-observation.json

python -B tools/managed_observer_smoke.py long-gate
  --job SCRATCH/job --output SCRATCH/observer --record expected-long-gate-rejection.json

python -B tools/managed_observer_smoke.py short-cold
  --job SCRATCH/job --output SCRATCH/observer --audit-output SCRATCH/audit
```

`SCRATCH` denotes that exact root. The producer command runs with cwd at the
frozen 763 source and explicitly supplies the real 312 summary. The launcher's
`launch.json` fixes the actual driver identity. Live observations run while the
producer is active; the final observation runs after the recorded driver exits.
The 60-second `long-gate` call must reject the unchanged 21,600-second/5,400-round
gate and must not create a long-run receipt.

`short-cold` is separate engineering-only evidence. It accepts only an actually
cold, fully reconciled 60-second/15-round snapshot whose remaining long-run
blockers are exactly the missing six-hour duration and long-run receipt. It
independently probes the actual report-selected Python/SQLite runtime, makes a
bounded **private complete** SQLite clone including exact validation sidecars,
and invokes that exact Python with
`benchmarks/run_managed_soak.py audit --directory PRIVATE_CLONE` from the frozen
763 source. Its before/after independent golden/FK/business/checkpoint
watermarks must agree. The nonce-bearing full clone is private and normally
removed; only `audit/short-smoke-cold-audit.json` is eligible for reviewed export.
That file explicitly says smoke-only, `long_run_receipt_issued=false`,
`final_evidence_eligible=false`, and every long-run/production/10k flag false.

Preparation verification executed 50 one-CPU tiny tests in 1.490 seconds, OK.
They exercised short ordinary Python PIPE children and synthetic gate fixtures,
not the real minute service. Actual service evidence is a later execution record.
