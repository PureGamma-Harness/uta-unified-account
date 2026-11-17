# Proposed once-only full QA for frozen 6b7d473

This preparation does not authorize or execute the matrix. Root must separately
approve the final supervisor SHA and launch command. The source is frozen at
`6b7d473c0fbf92b17c146140c88eb2c25d38dce1`, tree
`b4f777545099eeae8d753b3189d12867fb612bad`, in
`/workspace/uta-stopped-owner-gate`. This plan and supervisor live in a separate
worktree so they do not enter that candidate's test-input manifests.

The earlier first PR22 CI error remains an error. The once-only four-case
instrumented component diagnostic passed; its independent review is
`c9c6fe891f7a4c9f3b9c05d231567c5d3d9ef88e`. It does not prove the unique CI
cause, cover the original Python3.11 build, establish financial readiness or
approve production. Its kernel publication ended halted=true; its detached
outer wrapper was exited/Z under PID1. There were 440 trace events, including
254 generic status-return labels, of which only 92 have complete lease fields.
Those 254 labels must not be called 254 fence/lease reads.

## Source and resource admission

The initial sparse checkout lacked formal, benchmarks and scripts. With root
authorization only same-commit tracked files were materialized: 563 files,
22,511,555 bytes, all Git blobs checked. HEAD and every existing runtime/test
blob remained unchanged and status remained clean. There is no full copy.

Before materialization, free storage was 18,300,563,456 bytes. Admission reserved
the existing 17,448,304,640-byte cohost floor, 256MiB for QA output/temporary peak,
the tracked input bytes and an 8MiB allocation allowance. After materialization
free storage was 18,276,425,728 bytes. Recheck floor+reserve before launch and
each runtime. During execution loss of the floor halts the current owned
synthetic session and stops the matrix with UNKNOWN. No old file is deleted
to make admission pass.

Preparation checked all 874 tracked QA-folder inputs and metadata against the
exact Git tree, including benchmark data used by tests. It separately records
the standard runner's exact 351-file selected input map. The unchanged runner
SHA256 is `e9bff08c57bb1296388bf346c9e88f25e14f1d234c87fa60677702216e2368cc`.
The selected map must exactly match both source maps in each actual summary;
the complete QA input map and executable hashes are rechecked before/after
each runtime. Full maps are in the retained prepare-only JSON.

## Exact commands and environment

CPU affinity is [4], sequential order Python3.10, Python3.12, Python3.13.
The three exact inner argv are:

```text
/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10 -B /workspace/uta-stopped-owner-gate/tools/run_validation.py --output /workspace/uta-spawn-full3-validation/6b7d473-first/python310
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -B /workspace/uta-stopped-owner-gate/tools/run_validation.py --output /workspace/uta-spawn-full3-validation/6b7d473-first/python312
/usr/bin/python3.13 -B /workspace/uta-stopped-owner-gate/tools/run_validation.py --output /workspace/uta-spawn-full3-validation/6b7d473-first/python313-sqlite346
```

Actual interpreter builds and SQLite versions will come from each original
summary. Historical labels are 3.10.22/SQLite3.53.1, 3.12.14/SQLite3.53.1 and
3.13.5/SQLite3.46.1; executable binary SHA256 pins are checked now and before/
after execution. These labels do not substitute for actual future summaries.
Inherited UTA_* overrides must be absent; PYTHONPATH is removed for each QA
child; PYTHONDONTWRITEBYTECODE=1 is set. The remaining host environment is
inherited, without printing secret-bearing values. No H0 private-case or legacy
source override is added to this different candidate.

Each invocation uses the candidate's unchanged standard run_validation.py,
including its existing full unittest discovery, real OS raw-descriptor capture,
before/after manifests, clean-source gates and original summary semantics. All
case limits, including 4s publication and 0.6s leases, stay unchanged. The new
source predicts 1,813 tests (original 1,801 plus nine model and three native
registration cases); an actual count mismatch fails this plan's acceptance.

## Persistent supervisor and boundaries

After separate root GO, the one launch command from the plan worktree is:

```sh
python -B tools/run_spawn_recovery_full3.py --execute
```

The launcher creates only the new private output root, writes its fsynced
admission and launches a detached supervisor with start_new_session=True,
stdin=/dev/null and direct persistent stdout/stderr files. The supervisor is
not an attached functions/exec-server session. It remains alive when the
interactive launcher/tool returns or its transport disconnects. Launch birth/
boot/session identity is durably recorded and parent stream handles are closed
before a one-byte inherited-pipe GO is sent. A visible ACK file alone is never
GO; fsync/close failure or launcher death before release leaves the pipe closed
and the supervisor performs no QA. Pre-GO failures pin/kill/reap only the new
supervisor and preserve UNKNOWN. The supervisor verifies the pipe handshake
and its own source before writing supervisor-ready.json and starting QA. A later
PID1 zombie after its normal exit remains an explicit host-reaper boundary.

The original H0 admission actually recorded 900s per full suite, so this plan
retains 900s per runtime. It does not substitute the observed ~425s duration
or the earlier illustrative 600s figure. Overall userspace budget is 2,730s,
covering at most 2,700s active runtime plus cleanup. A new runtime requires its
full unchanged 900s and a ten-second cleanup allowance. Output is capped at
64MiB for the whole new output directory; workspace reserve is 256MiB. These
are userspace bounds and do not promise recovery from kernel-uninterruptible
I/O or host loss.

Each QA parent has its own new session. Its PID, birth ticks, boot ID, group,
session, pidfd and actual CPU affinity are saved before waiting. Its leader
is deliberately unreaped until group cleanup is complete. Before a TERM/KILL,
the supervisor rechecks exact identity, the self-owned group/session, and the
absence of protected PIDs. The source-pinned original helper's group probes
and orphan-reaper code are reused. TERM/KILL allowance is two seconds each;
orphan-reaper allowance is five seconds. Exceptions preserve UNKNOWN and do
not start another runtime. No source DB or pre-existing process is adopted.

Protected PIDs include 4471, 8784, 310035, 310039, 310266 and 310269 plus the
original helper's protected list. The new source and all tests remain frozen.
No database from frozen909, a six-hour job, original CI, H0 or earlier native
diagnostic is opened by this supervisor.

## First-failure policy, originals and acceptance

Every runtime gets a new standard result directory and a first outer outcome.
The standard runner continues its own full suite as originally implemented;
it is not changed to failfast. On that first runtime's FAIL, UNKNOWN, timeout,
resource error, incomplete cleanup or source change, the matrix starts no
following runtime and performs no retry. Later labels remain NOT STARTED;
missing reports are not reconstructed as passes. An unexpected supervision
exception writes a first UNKNOWN outcome and an incomplete matrix result.

All three actual summary.json, worker-result.json, unittest.txt and outer
first-outcome files are required for complete acceptance. Their exact byte
counts/digests, real commands and identities remain private originals; safe
publication is a separate read-only archive/review step. Check zero failures,
errors/skips/expected-failures/unexpected-successes, exactly 1,813 actual tests,
matching worker/summary results, source maps and raw-log digest, clean source,
normal reaped leader, no watchdog and successful matrix completion within its
budget. A unit-level pass never repairs a missing outer completion record.

Prepare-only execution and eleven pure ownership/report-policy cases have
passed. These include visible-ACK/fsync failure withholding GO with direct-child
reaping, and a group-signal error still attempting direct-child reap/pidfd close.
The original eight-case result is retained separately. No full QA, financial SQL, process-fault probe, package build or capacity
test has been performed by this plan. Capacity 10k/s, HA, multi-node durability,
custody and real-funds approval remain outside its acceptance scope.
