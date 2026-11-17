# Registered orphan fault-injection validation

Date: 2026-11-17 UTC. Base: `af7abab`. Test commits: `67dbe22`, `c1f7e7b`.
All work was isolated in `/workspace/uta-orphan-acceptance`, branch
`test/orphan-handshake`. Production remains **NO-GO**. This is focused test
evidence, not release approval, throughput evidence, or a completed soak.

## Original failure and evidence boundary

The [push run 44018824285](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44018824285)
failed at head `8eeab43fcbc57f0c94701069109c230750f9926a` in Python 3.10
[job 133823150009](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44018824285/job/133823150009).
The separate [pull-request run 44018901056](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44018901056)
has the same head SHA and a successful conclusion. This difference must not be
rewritten as an all-green result for the push run.

The full original job log is retained at
`/tmp/uta-orphan-original-job133823150009.log`, SHA-256
`bea767cc6eaaf071bc2dff7f4dc57bc1b3fc2d82c7c4dadff804f5b5540a407f`.
It was downloaded with:

```sh
gh run view 44018824285 --repo PureGamma-Harness/uta-unified-account \
  --job 133823150009 --log
```

Raw failure excerpt, with the repeated job/step/timestamp prefix omitted:

```text
ERROR: test_new_parent_uses_registered_birth_identity_to_recover_sigstopped_orphans (test_durable_process.DurableProcessTests)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/runner/work/uta-unified-account/uta-unified-account/tests/test_durable_process.py", line 365, in test_new_parent_uses_registered_birth_identity_to_recover_sigstopped_orphans
    os.kill(prior["workers"][0], signal.SIGSTOP)
ProcessLookupError: [Errno 3] No such process

----------------------------------------------------------------------
Ran 899 tests in 134.329s

FAILED (errors=1)
```

The old helper reported worker PID integers before fault preparation. The
production supervisor checks every `.05s`; after a worker's `.6s` lease expires,
it can legitimately kill and reap that own child and spawn a new generation.
Thus a reported PID can be historical by the later external `SIGSTOP`. Stopping
one worker during preparation also starts its expiry/replacement race while the
test is still setting up the other shard. The original log proves the target
was absent at that call. It contains no birth-identity or lease diagnostics, so
it does not establish the unique sequence that produced that absence.

`HarnessRaceTests.test_supervisor_reaps_reported_owner_before_later_fault_injection`
now reproduces the relevant lifecycle with a real router: observe a registered
ready owner, pin its birth with a pidfd, stop it at an EX/SQLite writer safe
point, release the monitor mutex, and observe that exact process exit with
`-SIGKILL`. The same supervisor then advertises a registered real worker with a
higher generation. Historical SPAWNED/OWNED rows remain immutable, and this
normal same-parent replacement produces no `ORPHAN_KILLED` receipt. The test
never sends another signal to the historical PID.

## Confirmed crash handshake

The coordinator still runs actual spawn workers, `_run_worker`, initialization,
market publication, activation, admission, and immutable command receipts. A
top-level test-only spawn wrapper arms fault injection around the real
`ShardWorkerView.process_one`; production source is unchanged.

1. After the real original order succeeds, the coordinator acquires its monitor
   mutex and selects its current own Process handles.
2. Shard 1 stops itself between real `process_one` calls. The coordinator then
   acquires the actual EX router gate, proving that shard 1 holds no SH gate.
3. The coordinator arms shard 0. Shard 0 acquires the actual router SH gate and
   stops itself inside that context, before opening a SQLite transaction.
4. Before reporting, the coordinator confirms both current children are alive
   and stopped and matches their birth identities against current SPAWNED and
   OWNED records, coordinator, nonce, actual lease owner, authority, and
   generation. It retains the monitor mutex while waiting for deliberate death.
5. The parent pins both births with pidfds and independently confirms that SH
   succeeds while EX fails. The original named recovery test deliberately waits
   for the unchanged `.6s` leases to expire and rechecks both exact stopped
   identities before killing the coordinator. This exercises monitor protection
   across the entire TTL, rather than relying on preparation finishing quickly.

Both recovery cases assert two real stopped registered old orphans, immutable
original receipt, two exact pidfd-confirmed old process exits, higher new writer
generations and different owners, a new coordinator, complete market watermarks,
exactly two matching `ORPHAN_KILLED` birth records, a real paired trade with two
fills, ledger conservation, and customer USD units `199992000000` after fees.
Absent workers cannot satisfy these assertions.

The second real process case,
`test_new_parent_waits_for_unexpired_registered_orphans_before_pidfd_kill`,
starts recovery while at least one old persisted lease is still active. It
observes the actual production `pidfd_send_signal` call without replacing its
effect, reads the corresponding owner's persisted `expires_ns`, and requires
`CLOCK_BOOTTIME >= expires_ns` immediately before each real SIGKILL. Every final
repeat reached recovery with **both** old leases active. Example raw evidence
from the final Python 3.12 log:

```text
orphan-recovery-expiry-evidence {'active_at_start': [True, True], 'pid_boottime_ns_expires_ns': [(41421, 29343477836061, 29343471150472), (41423, 29343484640016, 29343379324512)]}
```

These observations exercise the actual new-parent orphan-recovery wait branch.
They do not substitute a WriterFence unit test or an ownership model for that
process branch. If a slow environment misses the active-lease setup window, the
test fails explicitly; it does not silently classify an already expired owner
as proof of waiting.

## Cleanup safety and retained development failures

Signals use own unreaped Process handles, self-signals, or a pidfd opened before
rechecking birth identity and UID. Cleanup ignores already absent processes only
as cleanup; absence never counts as successful orphan recovery.

A temporary test subreaper preserves its original setting and pre-existing
children. It discovers new adopted descendants by actual PPid and birth identity,
uses pidfds for final termination, and reaps with bounded polling/WNOHANG. It also
covers coordinator death between `process.start()` and SPAWNED registration.
Multiprocessing's resource tracker is established before the baseline snapshot
and preserved. No `waitpid(-1)` or unbounded `waitpid(pid, 0)` is used.

`test_reaper_cleans_unregistered_adopted_child_and_preserves_existing_child`
really spawns a coordinator that exits after spawning a stopped unregistered
child. The test observes adoption, verifies the child was killed and already
reaped on scope exit, and proves that a child existing before the scope remains
alive with the same birth identity.

Development red evidence is retained rather than overwritten:

- `/tmp/uta-orphan-handshake-first-py312.log`: the first new main test reached
  recovery but incorrectly expected public diagnostics to include `boot_id`;
  the assertion was corrected to use the exposed fields, while registry checks
  retain full birth validation.
- `/tmp/uta-orphan-handshake-repeat-{py310,py312,py313-sqlite346}.log`: a temporary
  `/tmp` repeat driver initially lacked the repository import path; no test ran.
- `/tmp/uta-orphan-handshake-active-first-py312.log`: the first descendant scan
  used `/proc/<pid>/task/<pid>/children`, absent on this kernel. The final helper
  uses `/proc` stat PPid and restores subreaper state even if baseline scanning
  fails.
- `/tmp/uta-orphan-race-unsafe-stop-red-py312.log`: the first independent race
  reproducer used a random instruction-level stop; one run did not observe
  supervisor termination within eight seconds. SHA-256:
  `366bef0b11f6804d2300858f55e93a237a5a131377f5bd3c1ea386981f1826b3`.
  Stopping during SQLite work could obstruct lease observation, but this log
  does not uniquely prove that explanation. The final reproducer confirms the
  EX/SQLite writer safe point before stopping. This separate red run is not
  evidence of the unique cause of the original CI failure.

## Final focused validation

The final source bytes were unchanged during these runs:

| Source | SHA-256 |
| --- | --- |
| `tests/test_durable_process.py` | `55241140bdfae622a722fadbad38c5078ca7384613ea5239321ee63a705febc9` |
| `tests/test_orphan_harness.py` | `f8a7fe2ac1f5c273ff848d1e86b3baf0bd094f120c58facbda5319abc3052739` |

Each interpreter ran the two real recovery cases and the two harness cases five
times, with `-W error::ResourceWarning`. All 60 final executions passed; all 15
active-recovery observations reported `[True, True]`. Raw final logs contain no
ResourceWarning, traceback, or failure:

| Interpreter / SQLite | Result | Raw log | SHA-256 |
| --- | --- | --- | --- |
| Python 3.10.22 / 3.53.1 | 20/20, 29.540s | `/tmp/uta-orphan-handshake-acceptance-py310.log` | `fe3dddc94f88d6279ea9b042108a19a6d24be9f70e28ad1960cef6e4dd526fb4` |
| Python 3.12.14 / 3.53.1 | 20/20, 31.865s | `/tmp/uta-orphan-handshake-acceptance-py312.log` | `60cb88b1e1f5771ecf4104b75c72ae9c0951ca8bd12dbfe06073577476687679` |
| `/usr/bin/python3.13` 3.13.5 / 3.46.1 | 20/20, 30.581s | `/tmp/uta-orphan-handshake-acceptance-py313-sqlite346.log` | `b57c904b3ed10ca336603e9abf55f979e2e51253a3374514a85aa4dec765ed94` |

To run one focused round from the repository root, substitute the desired Python
interpreter:

```sh
PYTHONPATH=tests python -W error::ResourceWarning -m unittest -v \
  test_durable_process.DurableProcessTests.test_new_parent_uses_registered_birth_identity_to_recover_sigstopped_orphans \
  test_durable_process.DurableProcessTests.test_new_parent_waits_for_unexpired_registered_orphans_before_pidfd_kill \
  test_orphan_harness.HarnessRaceTests.test_supervisor_reaps_reported_owner_before_later_fault_injection \
  test_orphan_harness.HarnessRaceTests.test_reaper_cleans_unregistered_adopted_child_and_preserves_existing_child
```

The repeat driver is retained at `/tmp/uta-orphan-repeat.py`, SHA-256
`884fadcdc4c5903eaf75ba9d21b5327953a66f0939699e09488cd3ef41bb3f1a`;
the final logs above cover all four cases.
The committed tests and command above are the reproducible specification.
Only the two test files and this new document were changed. Runtime, lease
duration, business timeouts, production ownership rules, and existing soak
sources/jobs were not changed.
