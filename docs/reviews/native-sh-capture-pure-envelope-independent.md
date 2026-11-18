# Independent CODE closure of the pure-once execution envelope

Decision: **NSHC-CODE-001 CLOSED in static scope** for immutable source
`f434389bc68e17877ec96e5f429e33a543571446`, tree
`a337d4fd5a01d98a0beec8716c2a38b565fb3f3a`. This closes the execution-envelope
finding in independent review `00f2c60f4d17e4358a1692f61519a0873fce1970`.
It grants no execution GO and records no test result. Root must explicitly
authorize the complete pinned once-only invocation before any target execution.

This is a second read-only source review on 2026-11-18 UTC. No driver, target,
AST guard or pure method was compiled, imported or run. No trace, SQLite,
worker, PID/proc/pidfd, signal, network or capability probe was performed.
The absolute Python path's canonical resolution was inspected as file metadata;
the interpreter was not invoked. The original fixture source remains NOT_RUN,
not RED. The prior report remains unchanged to preserve its historical finding.

The new source adds exactly three files to fixture commit
`47b1c2cfd8c3d2e1b9c47eb10d407c5d720d1991`: the pure-once driver, its plan
and the envelope document. The entire `uta/` directory, original fixture,
eight-method file, financial fault test, AST guard and old closure have no diff.
Measured driver, plan and document hashes match the submitted frozen identities.

The closure is supported by these concrete source properties:

- The required CLI binds exact full commit, plan SHA and driver SHA. A new
  physical output directory outside the checkout is created exclusively with
  mode 0700; fixed artifact files use O_EXCL, O_NOFOLLOW and mode 0600. Existing
  namespaces are rejected rather than rewritten. There is no retry or native
  mode. Root must supply the reviewed identities and a genuinely new output
  path, not infer authorization from `--execute`.
- The outer process pins itself to CPU 1 before Git preparation and verifies
  actual affinity; children inherit that affinity. It verifies each enumerated
  physical file's regularity, bounded length, SHA, stable metadata and exact Git
  blob. The plan is independently pinned and checked against its Git blob.
  Execution inputs are retained buffers in the capsule, not later source reads.
  Physical source and plan identities are checked again after the host exits.
- The child command is explicitly `/usr/bin/timeout --signal=KILL 10s`, then
  `/usr/bin/taskset -c 1`, then the pinned absolute Python with `-I -S -B`.
  The bootstrap verifies the bounded capsule and driver bytes before compiling
  the retained driver. This is a host-interpreter timeout; Git preparation and
  post-verification are separate. The extra drain/reap window does not change
  the interpreter's timeout or authorize another attempt. The code does not
  inspect, adopt or signal an earlier worker or protected PID.
- One parent selector drains both child pipes into a single `SharedRaw` budget
  of 262144 bytes. Its payload ceiling is 261632 bytes, retaining 512 bytes for
  one trailer. It reserves permitted bytes before the FD write; overflow,
  exception or short/invalid write makes failure sticky. Charged bytes are not
  refunded and subsequent payload writes stop. The collector continues draining
  while its own timeout controls termination. A final file-size check is a
  second consistency check, not the enforcing mechanism.
- The frozen read map supplies all files used by the eight selected methods,
  including the unchanged original AST reference. Required fixture and case
  globals are supplied explicitly. Only declarations and selected actual AST
  are executed; the real `capture_worker` is omitted and its namespace identity
  is an inert raising function. The unchanged case imports are not executed,
  so `-I -S` does not depend on a bare helper import or installed UTA package.
  The selection remains exactly eight methods and the original below-64 modeled
  scope; this review reports no measured trace count.
- The selected methods run with frozen Path reads and native/process/writer
  guards. The audit restrictions and mocks are defenses for the fixed source,
  not an OS sandbox or a guarantee against arbitrary hostile code. Constructing
  the reference worker code object is not invoking a native worker or proving
  equivalence to a loaded production runtime.
- BEGIN is instrumentation metadata. Inner END uses a separate bounded control
  record. Parent PASS requires matching attempt/source and complete inner END,
  exactly eight tests, zero skips, actual host exit 0, actual reap, EOF on both
  raw pipes, no source/plan drift and no quota failure. A complete test failure
  remains FAIL; missing control data, timeout, incomplete reap/EOF or drift
  remains UNKNOWN. Sticky raw failure overrides success with UNKNOWN/125.
  First raw stdout/stderr, actual host exit, input checks, quota facts and final
  classification are retained under exclusive fixed names. No summary replaces
  the first raw files.

The timeout and pipe protocol are source-reviewed, not observed on this host.
There is no assertion that the first run will pass, that CPU 1 is usable at the
future execution instant, or that storage and OS termination have been tested.
Before-host rejection remains an envelope rejection rather than a test failure.
The outer process only waits for its new timeout child; incomplete ownership
completion is reported UNKNOWN and provides no permission for an ad hoc retry.

Original L1456 setup undo, L1461 capture exhaustion and L1525 actual five-second
recovery remain separate failed phases. Neither this closure nor a later pure
PASS proves native SH capture, native trace/code identity, original recovery,
the PR37 cap's effectiveness, capacity or production readiness. A native case
requires a separate explicit GO and a fresh synthetic authority. Rollback is
to leave the new envelope unused or revert its three added files, preserving
all original evidence and every subsequent first attempt.
