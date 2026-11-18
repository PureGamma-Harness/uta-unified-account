# NSHC-CODE-001 closure: prepared pure-once envelope

Status: CODE ONLY, NOT_RUN, zero target attempts. Original fixture commit 47b1c2c
remains NOT_RUN; its absence of an execution envelope is not a RED result.
The fixture, eight methods, original assertions and original 47b source-closure
JSON are unchanged. Independent review 00f2c60 closed their static semantics and
left only this execution-envelope requirement open. This document and the new
driver require a new independent CODE review and explicit root once GO.

The sole entry is `tests/native_sh_capture_pure_once.py`. After root freezes the
final source commit, plan SHA and driver SHA, the complete invocation is:

```text
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -I -S -B /workspace/uta-native-sh-capture-design/tests/native_sh_capture_pure_once.py --execute --output ABSOLUTE_NEW_PRIVATE_DIRECTORY --source-commit EXACT_FINAL_40_HEX_HEAD --plan-sha256 EXACT_FROZEN_PLAN_SHA256 --driver-sha256 EXACT_FROZEN_DRIVER_SHA256
```

Those three identities must be supplied by root from the final reviewed closure;
they are required arguments, not inferred GO. The output directory must be new,
physical and outside the checkout. `mkdir` creates it exclusively with mode0700;
all fixed artifact names use O_EXCL, O_NOFOLLOW and mode0600. Existing or spent
namespaces are rejected without modifying their first files. No retry option or
native-mode option exists. Before Git preparation the outer process binds
itself to CPU1 and records its actual affinity; its Git children inherit that
same single CPU. It never substitutes another CPU if CPU1 is unavailable.

The outer driver verifies actual Git HEAD against the supplied full commit and
compares every enumerated file with that commit's Git blob and the plan's length/
SHA. Physical reads require a bounded regular file, reject symlink paths, and
retain dev/inode/size/time/mode/owner/link metadata stable across the read. This
includes the fixture, eight-method file, original test/AST guard/reference,
unchanged 47b closure, runtime, this envelope document and the driver itself.
The plan has its own supplied SHA, exact Git blob and physical before/after
identity checks. Inputs are rechecked after the host exits; drift is UNKNOWN.

The retained bytes become a mode0600 immutable-input capsule. Its exact SHA is
passed to an inline bootstrap whose literal source is itself covered by the
driver pin. The child opens that capsule once, checks stable regular identity,
size and SHA, then compiles the driver from those validated bytes. It never
loads another unpinned driver file. Every later target compile/exec uses the
retained buffers. Apparent Path.read_bytes/read_text in the unchanged eight
methods are served only from the frozen map; arbitrary source reads/writes are
rejected. Parent-side post-reads are verification only, never execution inputs.

The outer driver actually launches this host command, recording its exact
arguments/bootstrap SHA in `intent.json`:

```text
/usr/bin/timeout --signal=KILL 10s /usr/bin/taskset -c 1 /opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12 -I -S -B -c PINNED_BOOTSTRAP NEW_CAPSULE_PATH EXACT_CAPSULE_SHA OWN_CONTROL_FD
```

This is the hard ten-second host-interpreter timeout, not a cooperative Python
trace. Actual affinity must equal `[1]`; actual executable, Python version and
isolated/no-site/no-bytecode flags are recorded. Wrapper failure, missing inner
END, timeout or incomplete reap is UNKNOWN, never PASS. The parent allows two
seconds only to drain/classify and one bounded wait to collect the timeout
wrapper; those windows do not extend target execution or authorize a retry.
Only its own timeout process is waited for. No old worker or protected PID is
read, signalled or adopted.

Both child stdout and stderr, including bootstrap, taskset, timeout and native
FD output, arrive through pipes. A single parent collector shares a total
262144-byte raw budget and independently withholds 512 bytes for one trailer.
It reserves the whole permitted request before each FD write. Capacity overflow,
exception, invalid write or any short write sets a sticky125 state; charged
bytes are never refunded and no further payload is written. Excess pipe bytes
are discarded while the timeout still owns termination. One bounded trailer
attempt uses only the held reserve. The first raw stdout/stderr files are never
rewritten or summarized in place. An outer raw failure overrides even a complete
inner success as UNKNOWN/125. Actual file sizes/hashes are retained as a second
check; a post-exit size check is not the enforcing mechanism.

Inside the interpreter, the sole selection remains the eight named methods and
below64 modeled traces from 47b. Only their class/fake declarations and required
actual fixture AST are compiled. The actual `capture_worker` target is replaced
in this memory-only namespace with a raising inert identity; no real trace or
worker target is called. No repository package or bare helper import is relied
on under `-I -S`; exact fixture globals and the frozen read map supply that
import context. The original standalone file and its fixtures are not edited.

Native/process/network imports and audit events, physical source opens, writer
operations, process wait/signal/pidfd, affinity changes, thread start, sleep,
trace/profile installation and product/database imports are denied during the
selected methods. These are defenses for the fixed reviewed source, not an OS
sandbox or a hostile-code security boundary. They do not prove native behavior.

`NSHC_PURE_BEGIN` is raw instrumentation metadata. A bounded private control FD
records `NSHC_PURE_END` with the exact attempt/source, all eight cases and actual
runtime/affinity. After both raw pipes reach EOF and the timeout wrapper has
actually been reaped, the outer driver records its unmodified actual exit in
`actual-host-exit.txt`, input post-checks, raw hashes and quota state in
`execution.json`, and `END.json`. PASS requires complete matching inner END,
eight cases, zero skips, host exit0, EOF, actual reap, no source/plan drift and no
quota failure. A complete test failure is FAIL; everything incomplete is UNKNOWN.
Exceptions preserve a bounded ENVELOPE_UNKNOWN record with actual known host
attempt/exit/reap facts; before-host rejection is not called a test failure. Missing
files/END are never inferred successful. All first failures/timeouts remain first.

The raw `.txt`, control/intent/execution/capsule/END `.json`, driver `.py` and this
`.md` are selected by existing literal extension rules in MANIFEST.in. No new
wildcard or omitted checksum extension is introduced.

This closes only the proposed pure envelope. It does not authorize or execute
SQLite, native SIGSTOP, PID/proc observation, actual trace installation, kernel
flock, product workers, CI, push or a fresh authority. A future native case still
needs its own root GO, source/authority identity and untouched first evidence.
