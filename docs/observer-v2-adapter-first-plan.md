# Compact-v2 adapter first-run proposal

Status: **CODE/PREP ONLY; NOT_RUN; no execution budget is implied.** The
previous distinct mock pipeline seal `e9fb25992f03edd36a7c5e25554c1e7c5f0c4a93`
records twelve SQL-free in-memory methods, not real buffered pipe or filesystem
evidence. Their first raw results and source remain unchanged.

Runtime change `b35d971041039474e6c6ba8a82215da308715008` addresses a CODE
finding made after that seal: default Popen stdout is a BufferedReader, and
`read(65536)` can wait for a full block or EOF. Only stream-mode stdout now
uses `read1(65536)`; captured legacy stdout and stderr retain `read(65536)`.
There is no blocking-read fallback. This source change is not yet validated
against a real pipe. It does not assert a hard I/O or shutdown deadline.

Frozen candidate source is `3e42ea9c09e747c2e843813907e4f8a6b33d0667`.
The companion JSON lists the complete eight-file input closure. This plan is
for one fresh synthetic adapter execution, subject to a separate root GO;
it authorizes neither an old mock rerun nor an actual observer/controller main.

## Exact proposed execution and effects

Proposed command, from this clean worktree, is:

```text
taskset -c 1 timeout --signal=KILL 10s python -B tools/probe_observer_v2_adapters.py --execute-synthetic-adapters --new-output /workspace/uta-observer-v2-adapter-runs/read1-3e42ea9-once01
```

Root must first authorize the fresh output path and creation, if absent, of
its private owned0700 parent `/workspace/uta-observer-v2-adapter-runs`.
The parent must already meet that identity/mode requirement before the probe
starts. The output child must not exist. No existing run path is opened or
modified; no recursive cleanup or retry is performed. All new synthetic
artifacts remain for independent first-result review.

The probe imports only JSON/report/transport/coverage/output-budget utilities.
It extracts the actual `Pipes`, `Timeline`, `append`, `atomic_json`, `integer`
and process-identity definitions by AST, injecting standard-library helpers;
it does not import the controller or observer module, SQL or financial runtime.
The actual Popen uses an allowlisted data-only emitter, and the actual two
Pipes drain threads run. The emitter inherits only a small fixed environment.
Both probe and emitter install audit guards against SQL, network, further
children, process signals and ctypes loading. These guards are defense in
depth, not a kernel sandbox or authorization for arbitrary code execution.

The only data child emits and flushes one complete small frame, then remains
alive for up to3s awaiting its own fresh release marker. The parent has at most
1s to see that raw frame. In the first original Coverage callback it records
the child's exact PID/birth alive state, absence of stdout EOF and release,
actual BufferedReader class and frame size below65536B. Only after that
classification does it create the release marker. Subsequent frames2–4
exercise the actual two-entry raw queue; a full queue must be observed before
continuing. The consumer reads at most two FIFO frames per call.

The test checks four complete frames, exact original wire SHA256, child exit0,
stdout/stderr EOF, no live owned threads and `frames_complete=true`. Stderr's
original bytes are additionally retained0600/O_EXCL under the fresh control
directory, capped at49152B; success requires it to be empty. Stdout's actual
BufferedReader is not wrapped or replaced. No EOF or extra filler is used to
make the first small frame arrive.

The production DirectoryStore, DirectoryReceipts and publication callbacks
write under the same fresh observer output. Reopening read-only dependencies
must reconstruct every full canonical report exactly; the actual operational
Timeline hydrates the full reports. A reopened identical CAS put and exact
receipt query must not add bytes, append or consume Coverage again. A separate
zero-budget store must reject only after one full Coverage observation; its
prior classification is retained and it is not retried. This adapter callback
checks original Coverage consumption before export. It does not run the full
supervisor `classify_safely`/official-drain process path or prove actual
financial golden verification; those remain separate gates.

## Hard bounds, evidence and failure semantics

There are4 frames,3 synthetic command rows per frame, at most32768 pipe bytes,
one data-only child and two drain threads. Existing root-specified CPU1 and
outer10s KILL are unchanged. The probe has a5s work deadline and bounded2s
cooperative cleanup; finite callbacks and native I/O still need the external
deadline. Cleanup releases the emitter if required, drains at most two queue
items per iteration, joins threads and records child identity, exit and
thread state. It never sends a process signal. The outer timeout may kill its
newly owned test process group on deadline; a timeout is a first failure, not
evidence of successful cleanup.

CAS logical-byte cap is65536B. The unchanged actual
`measured_output_bytes(control, observer)` counts **all** files including CAS,
receipts, negative store, release, original child stderr, result and cleanup.
The probe checks a stricter131072B aggregate. This is a metadata measurement,
not a physical block quota. It neither changes the original2GiB policy nor
exempts CAS. Original outer stdout/stderr should be sealed separately O_EXCL,
with a combined100KiB limit; a launcher must count and report these diagnostic
bytes separately instead of hiding them in a claimed aggregate. All files in
the actual observer/control measurement continue to count.

Before execution, the launcher must compare all eight input bytes to Git at
the frozen source, record hashes, actual command, environment-independent
process identities, start/end/elapsed, exit/timeout and original bounded raw
stdout/stderr. Repeat the source closure check afterward. Source-budget keeps
`allowed_runs_without_further_root_go=0`; a separate immutable intent records
any actual one-run root authorization. This document is not that authorization.

`control/result.json` records checks **before cleanup** only. Final pass also
requires outer exit0, successful cleanup, unchanged source, bounded full
output, exact counts/hashes and the explicit live-first-frame evidence. A
later cleanup/export error cannot inherit a provisional pass. On error the
first traceback goes to original stderr; the primary error is not replaced
by a cleanup-write error. Missing cleanup or an externally killed process is
UNKNOWN/NO_GO. No automatic retry or old first-result overwrite is allowed.

This work does not change or resume the old paused909 run. It runs no actual
watch, SQL, business worker, matching engine, finance golden, crypto/key
operation, network, CI or six-hour workload. Even a future adapter pass will
not establish continuous stability, financial acceptance, capacity or
production approval. All those flags remain false.

## Rollback

Legacy remains the default report mode. A future v2 rollout can select legacy
only for a **new separately registered run**; never alter the old run or its
baseline. Revert `b35d971` to restore the previous stream read implementation
if needed, while retaining its known timely-small-frame gap and all first
evidence. The synthetic probe/emitter can be reverted independently; keep
their immutable evidence. No data migration is introduced by this adapter
proposal.
