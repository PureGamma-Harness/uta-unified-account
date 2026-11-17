# Test-only CLI SIGTERM failure evidence candidate

Base is 6b7d473c0fbf92b17c146140c88eb2c25d38dce1, the exact source of the
requested313 first ERROR archived in9951e84. This candidate changes tests only.
It does not repair or declare a cause for CLI shutdown, alter financial code,
extend a timeout, skip a test or change an old failed result. No real CLI, SQL,
worker, signal or AuthDB probe was executed for this change.

## Static trace and evidence gaps

The exchange SIGTERM handler raises KeyboardInterrupt. The serve_forever loop
unwinds into _drain_exchange; that function first calls ExchangeWorker.stop(),
which sets its stop event and joins its non-daemon thread without a timeout.
After that it calls GatewayServer.server_close(), whose ThreadingMixIn uses
daemon_threads=false and block_on_close=true. The worker can still be executing
an authority transaction/IO when its event is set; ordinary SQL busy waiting
can exceed the test's five seconds. HTTP close can wait for admitted handlers.
These are hypotheses, not observations of the failed process's blocked frame.

This fixed test does not enable batch admission. /healthz replies explicitly
close its HTTP connection. The original primary exception occurs after banner
and health assertions and SIGTERM, at process.wait(timeout=5). None of those
facts establishes whether stop/join, handler drain, scheduling, IO or another
condition consumed the failed five-second wait. The old CLI child identity and
PIPE data were not retained; no stack is reconstructed from unrelated CI SH
failures or the parent/QA-worker stack.

## Preserved natural business case and explicit observation difference

The synthetic CLI argv, environment, policy, permissions, selector/startup limit
5s, health timeout3s, SIGTERM call, exit wait5s, cleanup communicate5s and every
business assertion remain unchanged. The original case is wrapped only to
record stages and re-raise its exact primary exception. A normalized method AST
is compared with the original Git6b7 case, excluding its old cleanup and the
explicit evidence hooks/cleanup replacement and normalizing only PIPE IO flags.

Root explicitly authorized binary stdout/stderr PIPEs with bufsize=0 for this
single fixed synthetic case. json.loads accepts the banner bytes unchanged.
This removes TextIO/buffer read-ahead, so the bytes consumed by the original
readline plus the bytes returned by one communicate form the complete first
stdout stream, with no missing prefetch or duplicate prefix. Stderr comes from
that same communicate. This is an IO observation difference and can perturb
scheduling; it is not a byte-identical sampling of the original natural run or
a reproduction of its failure. No child bootstrap, faulthandler, extra signal,
thread collector, runtime hook or modified CLI entry point is added.

## What a future failure retains

The helper records the actual child PID/start ticks/boot/UID at Popen return and
parent/child states alongside each monotonic stage: startup wait/banner, health,
SIGTERM, original exit wait, primary failure, cleanup poll/kill/communicate/exit.
The earliest high-resolution observation is Popen return; the kernel birth is
recorded in start ticks. An absent/reused process is not silently bound to its
old identity. These observations do not authorize signals to a recorded PID.
Only the original test's Popen.kill cleanup is used.

Success creates no evidence directory and emits no notice. On failure a new
0700 directory is retained outside the source tree, default /tmp/uta-cli-sigterm-
failure-*. Files use0600. Before cleanup, identity/stage metadata and already
consumed stdout prefix are saved. After the original cleanup, stdout.bin,
stderr.bin, private argv and evidence.json retain the first untruncated observed
streams. Credential/config/database files are never opened or copied by the
helper. Raw output and argv stay private; public notice contains only stage,
identity, completeness, type, size/hash and cleanup status metadata, with no
raw output, credential contents, nonce, auth header, path or exception message.

A communicate timeout retains its original partial byte buffers and marks
streams incomplete/cleanup UNKNOWN. A returned communicate with no integer
returncode also cannot prove EOF/exit/reaping. Secondary cleanup/archive errors
do not replace a pre-existing primary exception. If cleanup is unknown without
a primary, the test raises CleanupEvidenceError rather than passing. Archive
failure is explicitly reported as archive_retained=false. The old test's
cleanup communicate result is no longer discarded. This is userspace evidence,
not a guarantee of retention after host loss or SIGKILL of the test parent.

## Authorized validation and next gate

Exactly one pure command ran: timeout10s taskset-c1 python-B
tests/test_cli_sigterm_failure_evidence.py. Seven cases passed in0.033s;
process wall time0.053s/exit0. The watchdog did not fire. Popen, SQLite connect,
os.kill and Thread.start are patched to reject any accidental real operation.
Fake clocks/identities model stream assembly, original-exception identity,
cleanup timeout/exception, missing confirmed exit, archive failure and no-artifact
success. A >40KiB suffix on each pipe verifies no diagnostic size truncation.
The seventh check binds the unchanged business AST to the original Git source.
CPU1 was configured by taskset, not a separately printed in-process affinity ACK.

This model run does not establish real process/pipe/SQLite scheduling behavior.
Another group must review the test-only patch and its stream/cleanup boundaries.
A later explicitly approved, independently bounded real invocation may validate
the helper. The previous five-second failure remains ERROR. No actual execution,
extra signal or child traceback bootstrap is authorized by this document.

## Rollback

Revert this test-only change or restore test_runtime_review.py from Git6b7 and
remove the new helper/model/reference files. No schema, API, stored funds,
runtime configuration or financial state changes. Keep all original failure
archives and any future private evidence. Disabling the helper restores the old
test's discarded cleanup output; it does not resolve the underlying shutdown.
