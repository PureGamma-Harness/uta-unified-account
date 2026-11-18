# Native SH controller c98: NOT_CLOSED, CODE only

The prepared controller at `c98a02679fcd86d90ace6161b316724b2f8a1867`
(tree `ee3073262df604efcfa5ce90395d11bf90a7725d`) is **NOT_CLOSED**.
Four control-boundary findings below block native authorization. This review
ran no controller, compile/import, runtime metadata probe, test, SQL, worker,
PID/proc inspection, signal or network operation. The schedules are static
counterexamples, not executed failures. Native attempts remain zero; c98 is
NOT_RUN, not a native RED. Prior pure evidence and ee225 are not native credit.

1. **Python shutdown escapes the registered cleanup boundary.**
   `tests/native_sh_capture_native_once.py:505-509` restores the original
   `os.waitpid`/spawn hook and closes ledger pidfd/procfd handles on exceptions.
   The CLI at 972-978 then raises `SystemExit`, allowing multiprocessing's
   registered exit function to run. Pinned `multiprocessing/util.py:353-360`
   iterates active children and joins them without a timeout. A residual child
   after failed original cleanup can therefore enter an unregistered wait after
   the ledger has been dismantled. The actual factory does not set daemon, so
   its financial workers default to non-daemon: this review does **not** claim
   their daemon-only raw-terminate branch was reached. That conditional branch
   does exist at util.py:353-356 and delegates to popen_fork.py:46-57's raw
   `os.kill`. The definite selected-scope issue is shutdown's uncontrolled wait
   and lost registered reap accounting. The CLI needs an unconditional final
   exit boundary that survives flush/error-report failure and avoids Python
   atexit after explicit registered cleanup.

   The same exception-boundary issue starts earlier in outer setup: Popen is
   created at 630, but the owning resource `try/finally` begins only at 742.
   Session validation (646), durable ACTUAL_LAUNCH output (648), self-binding
   (653), selector setup and the first event write (661) can raise first. For
   example, EIO at 661 bypasses the later leader/socket/fd/reap cleanup. START
   has not been sent in this example, so no authority is credited and the CLI
   reports UNKNOWN; actual owned leader reap still lacks the promised finally
   protection. Protect ownership immediately after successful creation.

2. **Signal dispatch is not constrained by a shared absolute deadline.**
   ParentLedger.signal_record:273-279, TestSignal:369-393 and outer own_signal:
   667-675 contain no shared absolute51s check immediately before the actual
   pidfd signal syscall. The outer finally:879-884 dispatches even when its
   following reap loop already has no time left. A static example is entry to
   finally at t=51.01 with a held live child: the code still invokes SIGKILL.
   Another is event logging entered before the deadline but returning after
   it, followed by the syscall. A loop condition or SIGSTOP's earlier fixture
   lease check does not guard these dispatch points. Carry one absolute deadline
   into parent and outer, recheck after logging/IPC, and record UNKNOWN with no
   further dispatch after expiration. This cannot make an OS-blocked call hard
   real time; late return must remain UNKNOWN.

3. **A finalization delay can retain PASS beyond51 seconds.**
   The only final elapsed check at 843 precedes trailer output, three fsyncs
   (854-855), raw-file reads, END creation/fsync (874), and FINAL_OWNERSHIP/fd
   cleanup (876-918). Hand calculation: t=50.99 passes line843; line855's fsync
   returns at t=52; lines861-874 still write `NATIVE_SINGLE_CASE_PASS`/exit0,
   even while `actual_elapsed_seconds` itself can exceed51. Later finalization
   can also exceed the bound after that field is sampled. All late/partial
   finalization must prevent final PASS. An independently recorded actual outer
   exit/reap and monotonic end remains required; the controller cannot attest
   its own future exit. Preserve first receipts rather than overwriting them to
   hide a late result.

4. **Actual observer paths still use bare PID-based proc lookup.**
   The controller's kernel_records:431-438 checks a ledger entry but delegates
   to the original helper. That helper at tests/test_durable_faults.py:70-104
   calls original `_process_identity(pid)` and traverses `/proc/{pid}/fdinfo`
   and `/proc/{pid}/fd` by integer. The unchanged selected test also imports
   and calls the original identity function at 1341/1373/1416/1419/1457. Its
   implementation at uta/durable_process.py:393-398 reads bare proc paths.
   A retained controller proc-directory fd is not used for these operations.
   Static schedule: helper first verifies owner A; A exits and the supervisor
   reaps it; the integer is reused; the FD walk or next identity read touches
   the new process before a later birth comparison rejects it. Holding an old
   pidfd does not reserve a reaped numeric PID. This need not evade financial
   assertions to violate the new-subtree inspection boundary. Close these
   observer/identity paths with explicit case-only control adapters using the
   retained kernel references, or reject terminal/unknown ownership before any
   new lookup. Keep the original financial/runtime source and assertions pinned.

The reviewed positive boundaries are useful and remain CODE facts: deny10 is
present before controller-owned PID/proc/pidfd operations, with task TIDs checked
before their children files; creation receipts and BIRTH/ACK precede return to
the original spawn path; reservations precede the real creator; live financial
slots are capped at2, cumulative financial/tracker births at8/2; pending births
merge by matching birth and unresolved pending roles reject completion. Outer
uses its own new session/subreaper, held pidfds, and wait receipts; it contains
no group signal or global process walk. These findings do not endorse bypassing
the identified raw observer/shutdown paths.

The shared raw collector retains its 256KiB total including512 trailer reserve,
reserves before write and latches short/uncertain output. Events reserve before
write and have512/2MiB bounds plus cleanup allowance. The authority/evidence
sampling limits are explicitly logical, with50ms sampling and possible
overshoot, not filesystem quotas. PASS evidence requires terminal/reap and
source closure; the identified late-result and exceptional ownership gaps still
need repair before those claims are usable.

Static source closure checked69 regular non-symlink physical inputs,1512892
bytes, with each declared physical SHA/length and Git blob SHA/length equal to
the frozen plan. Five stdlib source SHAs match their pins. All UTA files equal
PR35@`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`; durable_process.py remains
`46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`,
without the later .1 registration cap. Original selected test, fixture, helper,
pure protocol test and envelope equal f434. The diff from immediate parent c42
has exactly the three new controller/plan/contract paths, so existing pure
originals and historical evidence are untouched. The first pure results remain
conditional pure evidence; no native/SQLite version was probed or inferred.

Frozen identities and machine-readable scope are in
[c98-code-review.json](../evidence/reviews/native-sh-native-independent/c98-code-review.json).
This is an independent review-only commit, not an author change, repaired
candidate, execution permission, performance claim or production approval.
