# Read-only stdin and partial-constructor ownership: unrun candidate

Status: **CODE/PREP ONLY, NOT_RUN.** Source
`9596eee193b9c75776f341a4e58126864a30d797` changes only the synthetic probe
and adds six focused pure-fake methods. The original dc1e first failure seal
`c9a0a12961cf26afe7242c3c8c17b54e391d002c`, all first raw artifacts and the
old frozen proposals remain unchanged. There is no second execution budget.

## Narrow descriptor substitution

Before installing its directory-write audit, the probe lstats literal
`/dev/null` and requires a real Linux character device with rdev major1/minor3.
It opens that path once with `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`, then checks
fstat type/rdev, device/inode against the pre-open identity and non-inheritable
state. Symlinks, a different device, replacement inode and verification errors
fail closed. Any post-open validation failure closes that owned descriptor.
No writable null-device descriptor or broad external-write exception is added.

Only the allowlisted single ChildAPI.Popen changes its exact DEVNULL stdin
argument to this already validated descriptor. stdout and stderr PIPE arguments
are unchanged. stdout remains the actual Popen BufferedReader consumed by the
actual extracted Pipes `read1`; no stdout wrapper, fake pipe or fallback to
blocking `read(n)` is used in the success path. This substitution tests stream
stdout behavior with equivalent read-only EOF stdin; it does not validate
Popen's original DEVNULL-opening branch, which remains recorded in the first
FAIL. The read-only descriptor is closed in `execute` finally. A close failure
fails a previously successful execution; when another error already exists,
that original error is retained and a new stdin-close UNKNOWN is recorded if
possible. Missing secondary evidence never grants a pass.

CODE inspection of the actual environment's CPython3.12 `subprocess.py`
(SHA256 `85d29b2bf0249f5436838298c9a60ee93508b1102e9ac43b001f8a7e7ae8f375`)
shows `_get_handles` uses an integer stdin FD directly. stdout/stderr PIPE
use `os.pipe`, and `_execute_child` creates an exec-error pipe, issues the
existing `subprocess.Popen` audit event and calls fork_exec with close_fds.
Those required descriptor operations need no directory-write exception.
Existing exact-command audit and forbidden-effect guards remain. This is
source analysis, not another child, pipe, null-device or interpreter test.

## Partial construction and unknown ownership

Popen is registered immediately when the real constructor returns, before
birth lookup or original-stderr wrapping. Birth failure leaves the original
Popen available for cleanup. The probe allocates the actual Pipes instance
inside the cleanup try before calling its unchanged `__init__`, so partially
initialized fields remain reachable. After construction, the Pipes process
object/birth must agree with the registered process/birth. A mismatch fails.

Cleanup first releases only the fresh private emitter marker, then uses the
same bounded2s cooperative window and at most two raw-queue drains per loop.
It sends no signal and creates no additional thread. If construction failed
before drain threads existed, its registered child's stdout/stderr pipes are
read nonblocking, with every captured byte preserved in fresh control files
under the same32768/49152B channel caps and131072B aggregate scope. It also
drains residual bytes through EOF after child exit. Already completed actual
drain streams are not read twice. This failure-only fallback does not replace
the read1 small-frame acceptance path.

Cleanup records constructor completion, birth establishment, exact binding,
child exit, created/live threads and fallback bytes/EOF separately. Unknown
birth, incomplete construction, missing exit or cleanup records cannot become
an adapter pass. Original errors survive cleanup errors; secondary failure
metadata stays within the same output scope. A future successful run still
requires outer0, source closure, child reaping, two completed real drain
threads, the original live-before-EOF proof and all original adapter checks.
No historical first-result is reclassified by this candidate.

## Proposed next budgets; neither is granted here

The new test file `tests/test_observer_v2_stdin_ownership_pure.py` has six
methods. It reads the actual probe source and executes selected actual AST
definitions against fake OS, child, stream, path, queue and virtual time
objects. It imports no probe module, actual observer/controller or SQL.
Its own audit rejects real writes, children, SQL, network, signals and ctypes.
It covers exact device/flags, invalid node/identity/non-inheritability,
stdin-only substitution and single-command guards, open/spawn/birth failure
registration, incomplete-constructor byte-preserving cleanup, bounded stuck
cleanup, FD-finally primary-error preservation and unchanged directory-write
rejection. This does not simulate a valid production financial workload.

Proposed first new pure batch: CPU1, outer KILL10s, six methods, at most32
small fake branches and original combined stdout/stderr at most100KiB.
No real null device is opened and no real child/pipe is created by this batch.
The new source-budget records allowed-runs0 pending a separate root GO.

Only after new review and another separate explicit GO may a **new** actual
adapter use `/workspace/uta-observer-v2-adapter-runs/read1-9596eee-once02`.
The existing parent must remain owned0700; that child must not exist. All
original limits remain: CPU1, outer10s, one fixed data child, two real drain
threads, four frames/three synthetic commands,32768 wireB,65536 CASB,
131072 measured control/observerB and separate bounded outer raw evidence.
The existing once01 directory is never modified or renamed. No old dc1e or
3e42 execution, mock12 rerun, observer/watch, SQL, financial worker, network,
crypto/key action, CI, long run or original-data access is authorized here.

Rollback is fixture-only: revert this candidate while preserving its source
and evidence. Legacy remains the default product/report path. No runtime
financial rule or data migration changes, and every production/capacity/
financial-six-hour acceptance flag remains false.
