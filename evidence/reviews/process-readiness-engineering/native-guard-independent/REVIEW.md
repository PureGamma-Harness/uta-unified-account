# Native outer guard independent review

Target: `0fbf6797b6a2f0c3bd8ed5782c303b024b48da90`, parent
`4179debef89bbc71f533be7756b12683969051e5`.
This independent sparse worktree adds review artifacts only. Target source,
the original two CI failures, the old unexecuted scope, and the original
seven-method first pure result are unchanged. No native GO follows from this
review, the fixture, or a caller-supplied hash.

## Result

**Changes required before metadata/native scope approval.** Three outer-guard
contract failures are supported by static source and the single authorized
synthetic AST batch. This is not a native test result, SQL evidence, original
CI reproduction, or production/capacity acceptance.

1. **Current protected PIDs can be inspected.**
   `native_once_common.py:12` excludes only 4471, 8784, 122905, 122907, 123007,
   and 123009. It omits the current protected 310035, 310039, 310266, 310269;
   the plan at line129 and manifest lines17-24 repeat that old set.
   `identity()` at lines83-92 reaches `/proc/PID/stat` for each omitted value.
   `discover()` lines205-210 consequently also permits binding such a PID if
   encountered in the owned child list. Preserve both old and current protected
   values and reject before any process inspection or signal path.

2. **Already observed deadlines do not stop new signals or native launch.**
   `native_once.py:281` checks 40 seconds only at the loop top; `drain()` at
   line224 may wait20ms. Entry at39.99 followed by an ordinary drain return at
   40.01 reaches lines313-318, which send TERM and KILL. The emergency loop at
   lines383-400 has the same shape. `BoundChild.send()` at common lines144-157
   has no absolute deadline, and its before-record fsync may return after the
   cutoff before it calls the signal primitive. The actual outer signal AST
   sent both fake signals at observed elapsed40.01; actual `send()` called its
   fake primitive after the fake before-record returned at40.02.

   There is also no budget recheck before Popen at line265 or gate release at
   line274. A preceding hash/fsync late return beyond45 seconds can still start
   and release the native case, then skip monitoring because it is already past
   40. This late-launch concern is static only; no Popen or native launch was
   exercised. Carry a shared absolute deadline through controller and runtime
   signal guards, recheck immediately before each new action and after the
   pre-signal durable append, and classify a missed action as UNKNOWN. This
   does not turn scheduling/fsync into a hard real-time guarantee.

3. **Successful writes followed by fsync failure bypass hard log caps.**
   Common lines74-77 add to `Journal.size` only after fsync succeeds.
   Controller lines235-240 similarly add to `stdio_bytes` after fsync. A write
   can succeed before fsync raises EIO; the next append/drain then admits bytes
   against the stale count. The unchanged Journal AST wrote104 bytes through
   a52-byte cap after one synthetic EIO. The unchanged drain AST started at
   2MiB-64 and reached2MiB+64 after the first write succeeded but fsync failed.
   Account for each successful write even if later durability fails, and seal
   an uncertain writer instead of allowing the stale count to authorize more.

## Verified boundaries and remaining limits

- The target diff adds exactly six files. Git/text comparisons show no change
  to parent runtime/test inputs or prior evidence. All69 manifest source hashes
  match target Git blobs:61 UTA modules,4 tests/helpers,4 runner modules. The
  declared plan SHA256 matches too.
- In normal sequencing, the controller binds a fresh-session leader and fsyncs
  `case_session_bound` before writing gate byteG. The case imports UTA and
  creates financial authority only after that gate. Same-birth checks include
  PID, start ticks, boot ID, UID and session, and controller signals use a held
  pidfd. These observations do not remove the deadline or protection defects.
- The preflight code itself starts no Git or other child process. Its SQLite
  metadata function imports sqlite3/_sqlite3, reads version constants and its
  own maps, and hashes the executable/extension/loaded SQLite libraries; it
  does not call connect or execute SQL. Review Git subprocesses were ordinary
  read-only inspection, not execution of that preflight.
- The64MiB business budget is a sampled stop threshold, not a filesystem hard
  quota. Normally bounded logger allocations fit below8MiB; the write/fsync
  failure path above defeats the claimed hard per-writer caps.
- Missing/late completion or exit/completion disagreement must remain UNKNOWN.
  Native finalizers and kernel calls are not hard real-time bounded. The manual
  final GO must come independently from root's engineering authorization;
  source/preflight hashes and caller fields cannot supply financial approval.
- The other reviewer owns case semantics and exporter completeness. A static
  cross-check also found the unchanged runtime's orphan recovery reads historic
  registry PIDs (`uta/durable_process.py:1224`) and has a direct pidfd KILL at
  line1259 outside this new `BoundChild.send` wrapper. The selected case restarts
  after offline faults, so historical PID reads are relevant. This review did
  not prove that a fresh execution reaches that KILL branch; do not call it a
  demonstrated native signal or assume every primitive is wrapped.

## Single authorized synthetic batch

Freeze commit: `2e84ac14417156f939dc34607186ba635daea213`.
Fixture: `guard_counterexamples_once.py`.
Fixture SHA256: `e26240b7403910fb32befd4b3370695fd3fc3c48cdd235e92b70704f0089e196`.
Actual target source SHA256 pins:

- `native_once.py`: `4926570fc7b86b3ea75317fc349c395724b350f3975cb24997d254eee54a8d6e`
- `native_once_common.py`: `a1d4a8be96fc4694ce0679cd6beb77ab82cf7826bc1fb9a784a1c312dc9f8838`

Root separately authorized one CPU-number4 /10-second /at-most8-method batch.
The frozen fixture ran once with actual affinity `[4]`, six methods,
0.2061658000020543 seconds, **one PASS, five FAIL, zero ERROR, actual exit1**.
The positive control rejects an existing protected PID before any fake proc
read. Five failing safety assertions demonstrate the defects described above;
they are not failures from the native readiness case.

The fixture reads the two frozen source files, verifies their SHA256, selects
unchanged AST definitions/subtrees and executes only those with fake Path,
identity verification, signal/pidfd primitive, file writes, fsync and time.
No target module is imported. No real/protected `/proc`, real signal/pidfd,
worker/child process, UTA, SQLite, network, old raw data, old seven methods,
metadata preflight or native case is exercised. Synthetic file-write sizes are
in-memory counters; no simulated log payload is written to disk.

First stdout/stderr and actual exit were captured with shell noclobber in a
new0700 scope, synced, hashed and changed to0400. They were not rerun/replaced:

| Artifact | SHA256 |
| --- | --- |
| `first-synthetic-2e84ac1/stdout.txt` | `0e54a91cff1f3078cd10114e8ed30b7963cc84fa00a39ebcdaeaa2d89f696e4a` |
| `first-synthetic-2e84ac1/stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `first-synthetic-2e84ac1/exit.txt` | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |

The shell wrapper's tool status is not the fixture exit; `exit.txt` retains1.
All subsequent native execution remains unauthorized by this review.
