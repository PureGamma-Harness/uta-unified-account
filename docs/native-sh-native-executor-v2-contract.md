# Single native baseline executor v2 — CODE ONLY / NOT_RUN

This new contract supersedes the executable claims of c98 without changing its
original contract, plan or zero-attempt history. Independent CODE review
8112e785a24290706f690e34b437814147d7771a found four blocking control defects in c98;
they were not executed counterexamples or RED native results. This v2 is also
uncompiled, unimported and unexecuted. It needs a new independent CODE review and
a separate exact root native GO. Metadata/proc/PID/SQL/worker/trace probes are not
authorized by a source freeze.

The only proposed outer argv is:

```text
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -I -S -B /workspace/uta-native-sh-capture-design/tests/native_sh_capture_native_once.py --execute --output /workspace/uta-native-sh-baseline-native-v2-once01 --source-commit EXACT_REVIEWED_HEAD --plan-sha256 EXACT_V2_PLAN_SHA256 --driver-sha256 EXACT_V2_DRIVER_SHA256 --envelope-sha256 e28b7f3272b544f9f65fdb477d6968028f14c506c119536f4113fb61b8ebe101 --sqlite-version EXACT_ROOT_APPROVED_SQLITE_VERSION
```

Root must independently record the exact first intent/argv, monotonic start/end,
launcher original stdout/stderr, actual controller exit and owned reap. The
controller's pre-exit observations cannot attest a future return. A timeout,
late actual exit, missing/partial END or incomplete role terminal record is
UNKNOWN and must retain the first output without rerunning.

## Unchanged source and native propositions

Baseline source is PR35/6010 runtime SHA256
46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219.
It contains no PR37 registration cap. The runtime, native fixture, original
test and financial assertions are byte-identical to c98/f434. One original
TestCase.run retains original setUp, method, finally and addCleanup order.
There are two original shards and at most two live financial workers, with
financial cumulative births limited to eight and tracker births to two. Normal
three births are not a guaranteed product maximum. The budget is reserved before
the actual creator call; exhaustion is UNKNOWN, never a reason to reduce the
original topology or repeat an uncertain spawn.

The original five-second capture, lease and recovery periods, >350ms control,
real EX/native SQLite writer observation, replacement generation, READY,
publication/reconciliation, financial/schema/cache assertions and fifteen-second
publication lifecycle watchdog are unchanged. The original method is called
once. No financial function, class, signature, engine fingerprint, _run_worker
CodeType or original native assertion is replaced or bypassed.

The extra fixture SH FD is an actual test-tool FD held by the real owner PID on
the same kernel router gate. It is not claimed to be the financial worker's
original critical-section FD. ARM/ENTERED is only rendezvous; the parent still
requires the actual active lease, creator-held pidfd/birth and kernel SH record
before its one actual SIGSTOP. It subsequently checks real T/retained SH and
writer/EX evidence. READY comes only from the real matching new PID/generation
report or one nonblocking pass over already available real pipe messages.
There is no recapture, delay extension, manufactured READY or retry-until-green.

A later cap candidate requires a different pinned source accepting only runtime
f2093101...19ca, a fresh authority and a separate first record. Neither old pure
PASS nor ee225 nor any CI failure is credited as a native result here.

## F1: lifetime ownership and no multiprocessing shutdown escape

The resource try/finally begins before Popen. Every statement following a
successful new Popen return, including child socket close, identity/session bind,
ACTUAL_LAUNCH fsync, self bind, selector registration and first OWNED_LEADER event,
is covered. An early EIO cannot skip the owning finally. The inner actor waits
for START_CASE before product imports/authority/workers. If binding never
completes, closing its private channel yields EOF and the outer waits only on
the actual new Popen creator handle within the remaining absolute budget. It
never guesses an identity or sends a bare/group signal.

Once positive binding exists, exceptions use only the retained new pidfd and
procdir records. Cleanup attempts real owned waits and nonblocking pipe drain.
FINAL_OWNERSHIP records unresolved facts as UNKNOWN; inability to write that
record also prevents a normal status. No missing terminal evidence is treated as
a successful reap.

The private case interpreter keeps registration/wait/identity gates and held
ledger fds until genuine os._exit. It does not restore raw stdlib callbacks or
close ledger fds during the final status-write interval, so a residual monitor
cannot create a gap through restored spawn/wait operations or reused fd numbers.
Its original normal TestCase teardown still runs unchanged.

Both CLI paths have an unconditional final genuine os._exit, including error
print, status persistence and stdout/stderr flush failures. Thus the selected
non-daemon financial children cannot enter multiprocessing util._exit_function's
unbounded join after the case returns. The stdlib daemon terminate branch exists
conditionally; no selected financial daemon-true fact is asserted. Unknown
residual actors remain the outer's held-new-subtree responsibility. Actual exit
and reap must still be independently observed.

## F2/F3: one deadline, dispatch and durable finalization

Outer establishes one absolute monotonic deadline at started+51 before writing
inner config; that exact value is bound by the config SHA and shared by case
parent, test-signal facade and outer cleanup. The case watchdog stays at 45s;
the remaining six seconds are cleanup/drain budget, not an extension to the
original five-second native recovery assertion.

All controller pidfd dispatch paths funnel through dispatch_owned. Protected
numeric denial is repeated and the common clock is checked after event/IPC/log
work, immediately before the actual syscall. At or after the absolute deadline,
no signal is sent and the result becomes UNKNOWN/incomplete. Finally cannot
dispatch a late SIGKILL. No blanket kill, old PID adoption or process-group
signal is available.

Raw trailer and END explicitly say PENDING_FINAL_RETURN and contain an observed
candidate, never a claim that finalization or future exit already succeeded.
There is no return inside the main resource try. After END, FINAL_OWNERSHIP,
descriptor fsync/close and cleanup, the same deadline is checked again. CLI
then durably writes its bounded PRE_EXIT observation, flushes, checks the same
deadline once more and uses genuine os._exit. A write/flush failure is nonzero.
The static t50.99 -> fsync52 example therefore cannot retain actual exit0.

These checks cannot prevent OS scheduling or filesystem operations from
returning late, and no hard realtime guarantee is claimed. The independent
launcher's actual monotonic end/exit/reap is indispensable; any actual elapsed
value above51s invalidates a candidate even if an earlier record proposed zero.
No earlier END field certifies a future return.

## F4: anchored test identity and actual kernel FD observations

The original test method and undo helper retain their local import statements
unchanged. A private-case import adapter returns the anchored identity observer
only for exact name uta.durable_process, fromlist (_process_identity,), level0,
and the original test module's identical globals dictionary. Every other import
returns the original module. The uta module and its real function/code remain
unchanged; the native worker's self-observation remains real.

The test identity adapter first denies protected numbers, requires the new
creator receipt/ledger record, rejects an exited held pidfd, and reads stat
through the retained proc-directory fd. It compares birth and returns the same
five original identity fields. It never reopens /proc/<integer> for an old test
binding. An exit/removal is an error, not a synthetic identity.

The case-only kernel adapter preserves every original kernel predicate: exact
bound identity before/after, real router-file dev/inode, real descriptor link
target and stat dev/inode, and parsed FLOCK ADVISORY READ PID/device/inode/0 EOF
records. Its fdinfo directory and every fd/readlink/stat access are relative to
the retained procdir (and fdinfo dirfd). It reads actual bounded fdinfo bytes
through EOF; it never calls the original helper that walks bare PID paths.
A descriptor that closes meanwhile is handled by the original missing-file
rule; disappearance of the bound process is an error. The additional 64KiB
fdinfo observation bound fails UNKNOWN rather than accepting truncated records.

Creation uses positive Popen/stdspawn/owned-children receipts before denial and
binding. Denial precedes all new PID lookups, pidfd opens and signals. New
subtree discovery uses retained task/children anchors and a bounded pending BIRTH
handshake, not a global proc scan. Invalid/duplicate BIRTH frames are rejected
before replacing a held pending record; a mismatch cannot close a still-registered
pending handle. New self and declared roles only are eligible. Protected numeric
collisions are not inspected or signalled; a kernel already-exited actual own
child wait receipt may only be reaped and rejects qualification.

## Resources, evidence and rollback

All actors inherit CPU1; original two-shard topology is retained. Shared raw
stdout/stderr limit is256KiB including512B trailer with reviewed reserve-before-
write/short-write sticky125 behavior. Events have512 entries/2MiB with32 entries/
64KiB cleanup reserve. Evidence is8MiB with256KiB final reserve; PRE_EXIT files use
that reserve. Output is a new0700 root, O_EXCL0600 artifacts and checked0444 private
source copies. No pycache is copied.

Authority logical size is sampled every50ms; above28MiB starts UNKNOWN cleanup,
leaving4MiB goal headroom within32MiB. This is not a kernel hard quota. Sampling
may overshoot and actual final within-cap state is required for normal acceptance.
Capacity/DR hard-quota validation is outside this scope. Data is retained without
trimming or replay.

The v2 plan pins all uta files plus selected original test, native fixture,
diagnostic/reference, controller, reviewed envelope and this contract by regular
physical bytes/length/SHA and Git blobs, before/after and in the immutable private
copy. Five reviewed stdlib spawn/wait source pins remain. The plan itself is
checked by its independent Git blob and CLI SHA, avoiding a self-hash cycle.

A normal accepted outcome requires original one test zero F/E/skip/expected
failure, real replacement READY, every role's actual terminal pidfd/wait evidence,
actual host exit0/reap, complete source/raw/END/FINAL records, and the independent
controller actual exit0/reap/end before the shared deadline. Otherwise preserve
original counts and UNKNOWN or FAIL; no retry is authorized. Only the separate
review may close these CODE findings, and only a separate GO may produce native
evidence.

Rollback means stop before START or use only this scope's positively held new
handles before its existing deadline, retain all first artifacts, and discard
the new source selection for any subsequent separately authorized scope. Never
change an existing authority binary, erase original CID/metadata, confirmed
trades, ledger rows, old CI raw or old first-result records. No push, CI, deploy,
production signing or old protected PID operation is authorized. Native attempts
remain zero for both c98 and v2.
