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
