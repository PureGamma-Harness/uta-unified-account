# Independent source review of instrumented SH capture

Reviewed immutable source `47b1c2cfd8c3d2e1b9c47eb10d407c5d720d1991`,
tree `a4e59daf18139e05c865816f888ca9e77edff56d`, against PR35 base
`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec` on 2026-11-18 UTC.
This review is independent of the fixture author. The candidate worktree was
read only; this report is committed in a separate review worktree.

Decision: the frozen test fixture's intended callsite, one-shot protocol and
preservation of the original recovery assertions are supported by static code
inspection. **First pure execution remains BLOCKED on the execution-envelope
closure described below. No execution GO is granted by this review.**

No target was compiled, imported or executed. No pure test, AST guard, worker,
trace installation, SQLite connection, process inspection, pidfd, signal, native
flock, network operation or capability probe was performed. The evidence here
consists of Git metadata/diffs, text reads and SHA-256 checks. Source inspection
of an AST guard does not mean that the guard passed.

## Supported source findings

- `uta/` has no diff from the stated base. The durable-process source digest is
  `46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`.
  PR37's SPAWNED registration timeout cap is absent.
- The real fault test changes only 11 added and one removed line. Additions
  select a fresh test-only profile, ARM inside the original five-second capture
  horizon, require ENTERED, send RELEASE before the original undo, and refuse a
  second capture. The existing recovery, finance and finally statements are
  unchanged by the text diff. The augmented existing AST guard removes only
  these explicitly enumerated additions before consulting its unchanged golden
  module digest; that guard has not been run in this review.
- The context proxy substitutes only the initial shard-zero Process target.
  Sibling and replacement workers receive the original target. The wrapper calls
  the unchanged native `_run_worker`; it does not replace UTA functions, code,
  signatures, verification modules or loaded-engine checks.
- The wrapper pins the runtime source digest and compares the loaded worker's
  CodeType to compilation of that exact source. Its selected AST call is the
  unique original `view.process_one` call, and tracing checks the actual worker
  code object and that line. In the frozen source this is after `_OwnedStartup`
  exits, and after its keeper has drained, with the read/transaction context
  managers closed. The child additionally refuses another trace owner, a wrong
  role, writer PID/generation/birth mismatch or remaining thread.
- ARM and subsequent envelopes are size bounded and contain a version, kind,
  birth-bound owner and finite positive deadline. Integer identity fields reject
  Boolean aliases. Actual child messages pass through the strict envelope
  reader before the state transitions. The state sequence is one-shot
  NEW -> ARMED -> ENTERED -> RELEASED -> CLOSED. Parent and child compare the
  same binding and original deadline; neither renews the lease.
- The held descriptor is explicitly additional test instrumentation in the real
  lease-owner PID. It uses the original router `_lock` default SH operation.
  Parent kernel-inode, stopped-birth, pidfd, EX exclusion and native zero-DML
  writer-availability predicates remain independent. This does not prove the
  descriptor came from an original financial critical section.
- On failed native predicates RELEASE precedes the existing SIGCONT undo. The
  child drops SH before sending RELEASED and parks outside SH until ABORT or
  the original capture deadline. It cannot enter `view.process_one` afterward.
  The parent still requires original live birth, SH absence and active same
  lease before its explicit one-shot refusal. Replacement workers follow the
  ordinary target, and cleanup restores the parent context and closes its own
  pipe endpoints. These static properties are not native scheduling evidence.
- The proposed driver has exactly eight test methods. It exercises the fixture
  helpers with fake gate/wire/clock/Process objects, enumerates 24 protocol
  permutations, constructs but does not invoke the worker code object, and
  selects the existing AST-guard method rather than importing the financial
  testcase. Its standalone main guards SQLite connect, worker/thread start,
  wait/signal/pidfd, flock, sleep and settrace. No claim is made that those
  guards ran or that all possible native capabilities are sandboxed.

## Required closure before first pure GO

`NSHC-CODE-001` — The frozen plan and source closure declare a maximum of one
CPU and 10 seconds, but the eight-method driver contains no enforcement of
either and no shared stdout-plus-stderr byte cap. No frozen external runner,
raw byte ceiling or timeout/termination ownership protocol is referenced. A
post-exit file-size check would not enforce a write cap.

Provide the exact separately frozen root-owned execution envelope before
running: one selected driver command, one CPU, an outer wall limit, one shared
raw write ceiling, and the rule for preserving first output/exit on failure or
timeout. Include all envelope dependencies and distinguish a hard outer bound
from cooperative Python checks. The child fixture/protocol need not be
redesigned for this finding. The target remains NOT_RUN until root gives a
concrete once-only GO for that complete closure.

The fixture import is `native_sh_capture_fixture` at top level. The frozen
repository's CI uses discovery with `tests` as the discovery directory; the
pure driver also works as a direct script with that directory on `sys.path`.
The future command must specify this import context. This review does not
certify an arbitrary fully qualified unittest module command from repository
root.

## Evidence limits and next decision

The source digests below matched the frozen worktree and the author's closure.
No source dependency from a different runtime was substituted. The unchanged
golden AST JSON remains the declared dependency; no golden recovery result was
regenerated. The finite pure plan's below-64 claim is a bounded selection of
small modeled scenarios, not a measured native trace count.

Original L1456 undo, L1461 capture exhaustion and L1525 five-second recovery
failures remain separate failed phases. The PR41 exact-head diagnostic's
registration/WAL stack is compatible with a conditional synchronous-monitor
blocking path; it is not unique causal proof. Deterministic capture cannot
itself close L1525 or establish that the PR37 timeout cap repairs recovery.

After the execution envelope is closed, root may decide on exactly one pure
run. A native run needs a separate fresh synthetic authority and explicit GO;
baseline and cap candidate must keep separate source/authority/first-result
identities. No protected PID or previously spent authority is a test target.
Production, real funds, capacity and HA acceptance remain unapproved.

Rollback consists of reverting these test/profile additions while retaining
the immutable first failed logs and all later first-run evidence. No production
runtime or schema migration is introduced by this candidate.
