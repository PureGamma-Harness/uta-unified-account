# Native SH executor v2: CODE CLOSED, NOT_RUN

The four controller findings in independent review
`8112e785a24290706f690e34b437814147d7771a` are **CODE CLOSED** for exact source
`48d045d478564f7ea15239e21f8164ca517339ca`, tree
`4ee064c8a94b9e6656295768b782975a3671e14c`. No further reproducible blocker was
found in this scoped static rereview. This closes source findings, not a native
qualification or execution permission. Both c98 and v2 remain NOT_RUN with zero
native attempts. The original 8112 record and its c98 NOT_CLOSED conclusion are
unchanged and still apply to that older source.

The review used Git/text, source-file byte counts/SHA and regular/non-symlink
checks only. It did not compile or import the controller, run a method/fixture,
probe runtime metadata, read actual proc/PIDs, open pidfds, send signals, launch
workers, execute SQL/native operations or access the network. No child reviewer
was spawned and no author source or old evidence was changed.

1. **F1: exceptional lifetime and Python shutdown are closed in source.**
   The outer resource try starts at line816 before Popen817. Child socket close,
   birth/session binding, ACTUAL_LAUNCH persistence, self bind, selector setup and
   initial event output all occur inside it. Finally975 handles an unbound
   creator through channel EOF and its actual Popen wait (993-1000), and a bound
   actor through retained records and deadline-guarded cleanup. It no longer
   skips owning cleanup on the old first-event EIO example.

   Parent finally590-596 deliberately retains the spawn/wait/import gates and
   ledger fds until the real process exit. It does not restore raw callbacks or
   close handles in the interval in which a residual monitor could run. The CLI
   is protected by finally1173-1181 even if error printing raises.
   finish_process1113-1155 catches PRE_EXIT persistence/close/flush/check failures
   and reaches the captured genuine `REAL_EXIT = os._exit` in its innermost
   finally. Thus those paths do not enter multiprocessing atexit and its
   non-daemon unbounded joins. Original TestCase normal cleanup still runs first.
   Missing/unreaped ownership and cleanup errors stay UNKNOWN/nonzero; they are
   not replaced with inferred success.

2. **F2: actual signal dispatch uses the shared absolute deadline.**
   The single absolute value is created at695-701 before config persistence and
   bound into the inner config SHA. The inner validates it at1094-1097 and passes
   it into ParentLedger at438. Parent signal303, test signal418 and outer
   signal737 funnel through dispatch_owned66-73; its line72 is the controller's
   only real pidfd signal syscall. Protected denial and monotonic deadline
   comparison occur after caller event/IPC work, directly before dispatch.
   Expiration returns false and the callers mark/raise UNKNOWN without signalling.
   Finally cleanup uses this same function, so the old t51.01 dispatch example
   is rejected. OS scheduling/blocking still prevents a hard realtime guarantee;
   a late return cannot establish a within-budget result.

3. **F3: durable finalization cannot retain an earlier PASS status.**
   Trailer946 and END960 now say PENDING_FINAL_RETURN, retain the observed
   candidate and explicitly disclaim future exit. There is no return in the
   resource try. FINAL_OWNERSHIP persistence, handle/pipe/selector close and final
   descriptor fsyncs all precede the final check1065-1068; their failures enter
   unknowns. finish_process then persists PRE_EXIT, flushes, rechecks after those
   operations at1150 and calls genuine exit. In the old t50.99 -> fsync52 static
   example, actual proposed/returned exit is126, while any earlier candidate
   remains only a pending observation. A final OS scheduling delay after the
   last clock check is still possible: independent actual controller monotonic
   end, actual exit and owned reap are indispensable. The external acceptance
   must reject a late actual end, nonzero exit or missing/partial terminal
   records; this review does not substitute early JSON for those observations.

4. **F4: selected test identity/kernel observers use retained anchors.**
   case_import566-573 adapts only the original test module's identical globals,
   exact module name, level0 and one-item `_process_identity` fromlist. This
   covers the unchanged selected method's and undo helper's local imports.
   Other imports receive the real module; financial/runtime source and worker
   CodeTypes are unchanged. case_identity228-235 denies protected numbers,
   requires a creator ledger entry, rejects terminal held pidfds, reads stat
   through the retained procfd and compares the birth before returning the same
   five identity fields.

   kernel_records458-514 no longer calls the original bare-PID helper. It
   preserves the actual router dev/inode, descriptor target/stat and full
   FLOCK/ADVISORY/READ/PID/device/inode/0/EOF predicates, with before/after
   identity checks. fdinfo enumeration, descriptor readlink/stat and fdinfo reads
   use retained procdir/fdinfo directory fds. The read is through EOF or fails
   above64KiB; it never accepts truncated evidence. The original per-FD
   FileNotFound handling is retained, while loss of the selected process is an
   error. The c98 numeric-PID reuse schedule therefore cannot redirect these
   actual observer operations to a new process.

Protected10 remains exact, including task TIDs denied before task/children file
access. Birth creation still reserves before the real stdlib creator, caps two
live financial workers and cumulative financial/tracker births at8/2, requires
outer BIRTH/ACK before returning to the original spawn path, and keeps pending
births fail-closed until the bounded handshake resolves. Invalid/duplicate birth
frames now reject before replacing pending ownership. Terminal pidfd state,
actual waits, missing-END, pending/unknown roles and watchdog conditions remain
part of acceptance. No global proc scan or group signal was introduced.

The unchanged original two-shard test is still called once, with its original
five-second lease/capture/recovery assertions and financial/schema/cache
assertions. The shared raw collector retains256KiB including512 trailer reserve;
events retain512 entries/2MiB and cleanup reservations. Logical authority/evidence
monitoring remains50ms sampling with explicit overshoot, not a hard filesystem
quota. This static closure makes no SQL, recovery, financial or performance
claim.

Closure checks matched69 regular non-symlink physical inputs,1526322 bytes, to
every declared length/SHA and exact Git blob length/SHA. All five stdlib source
lengths and hashes match their existing pins. All UTA files still equal PR35
`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`; runtime durable_process.py is still
46905e06...97219 without the PR37 .1 registration cap. Against c98, old native
plan93ebb40f..., original contracte1b4adfb..., fixture/test/helper/pure protocol,
reviewed envelope and first-pure original directory have zero diff. The v2 diff
contains only the modified controller and the two new v2 plan/contract paths.

Exact pins, closure facts and review scope are retained in
[v2-48d045d-code-review.json](../evidence/reviews/native-sh-native-independent/v2-48d045d-code-review.json).
Any future run requires a separate exact root GO, fresh one-shot output, approved
interpreter/SQLite identity and independent actual launcher/exit/reap evidence.
No actual SQLite identity has been probed here. Old pure/CI/ee225 outcomes are
not native credit, and production/real-funds approval remains false.
