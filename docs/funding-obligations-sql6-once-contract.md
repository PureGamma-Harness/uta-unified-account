# Funding obligations SQL6: frozen CODE proposal

This scope is **NOT_RUN / NO_GO until independent ENTRY/CALLER CODE review and a
separate root execution instruction**. It does not authorize a target import.
The financial and six-test source is `90e81daa7b7cb398664c1dadb3a0d943e45321d6`.
All 64 UTA files, the six original method bodies, their fixture, original 901/90e
plans and historical evidence are unchanged. FUND-OBL-001/002 have limited CODE
closure in the separate account/risk reviews; the 003 hypothesis was withdrawn.

## Fixed workload and independent expectations

One ordered, fail-fast suite selects exactly the six methods in the new plan.
The fixture's existing `UTA_FUNDING_OBLIGATION_CASE_ROOT` retains nine new
namespaces: normal, missing, current-data, capital, competition,
changed-positions, new-empty, old-empty and review. The driver wraps `scenario`
only to enforce order and retain its returned original objects; it adds no
financial setup, market repair, test assertion or database adapter. No original
test method is extracted or rewritten.

The independently registered per-namespace journal counts are
6/4/6/11/6/8/0/0/5, matches 1/1/1/2/1/2/0/0/1. Across independent authorities this
is 46 journal events, nine qualified matches and eighteen paired fills, USD .72
fees, USD -15001 custody, eight obligations, five APPLIED and three outstanding.
These are expected values, not measured results or globally unique trade IDs.
The new manual oracle fixes each balance, current quantity/cost, trade size,
fee/PnL, cut quantity/mark/rate, cut/current market version and terminal state.

After all six successful IDs and original connection closure, each new DB is
opened through a real `mode=ro` URI and `Database.read_transaction`. There is no
ordinary service/Matcher constructor or schema repair in this phase. The two
empty capability databases must still have no matching table, account or fill.
The independent oracle calls no UTA arithmetic, hashing, planner, fixture value
function or writer. It recomputes canonical ledger hashes and full materialized
balances with integer units, checks currency balance per journal, joins both
fill/order/journal sides, manually checks current positions, recomputes the
obligation command/event hash chain, cut digest and toward-zero cash legs using
Fraction, and checks receipt/cut/cash/current-risk references. Original component
verifiers are called separately in the same read snapshot and labeled as such.
The deliberate orphan in `review` must remain financially unhealthy and its
component funding verifier must reject `funding_reconciliation`; it is never
counted as a healthy funded authority. Schema inventory must remain unchanged.

## Resource observers and exact thread boundary

The only target threads are exactly two native ThreadPoolExecutor workers in
the original competing-executors test. Original Barrier(2), wait(5s),
future.result(10s) and executor semantics remain unchanged. The controller
allows the original Thread.start only for that fixed method and `_worker`
target, reserves each of two starts before native start, denies direct native
thread creation and denies every other method's thread start. No service
worker, background scheduler, network or extra target process is authorized.

SQLite connect/handle audit events accept only the nine exact rw/ro URI families
and original native `sqlite3.Connection` objects; each is strongly retained so
identities cannot be recycled. An explicitly declared resource-only
`sys.setprofile`/`threading.setprofile` observer records successful native
Connection.close `c_return` events in the closing thread. It does not infer a
connection from connect return counts, call connection attributes from another
thread, record frame locals, read money/nonces, replace connect/factory/close,
or alter a financial method. `c_exception` is not success; duplicate closes do
not count as different handles. Every successful close must identify an already
audit-observed object. Connect count, native handles and distinct nine URI
families must agree; every observed handle must have a successful close before
reopen and after reopen. At most 2048 connects and 4096 close returns are allowed.

The main and future-thread profiles initially must be None. A finally block
restores both profiles and thread entry functions even after first failure;
restoration has its own private file and must be validated outside the target.
The callback observes no frame locals and retains only bounded native handle
references/identities and counters. Callback exceptions, disabled/changed
profiles, a live thread, missing close event or failed restoration prevent PASS.
The main thread never closes an observed foreign-thread connection to repair
qualification. Original executor shutdown may block after a test fault; the
outer native target deadline is containment, not proof of cooperative shutdown.
Observer overhead is included and supports no performance conclusion.

## Proposed execution and capture envelope

The new entry reuses the already reviewed funding SQL retained-buffer loader
and shared stdout/stderr FD capture, under a new path and explicit scope. It
retains all inputs before execution, checks Git/physical bytes and runtime,
loads whole frozen UTA modules and runs one suite without retries. The caller
reuses the sticky normal-EOF/wait discipline of the decision-audit caller and
checks the new six-ID/nine-DB/observer evidence. Its new owned outer is stdin
gated, birth-recorded and held by pidfd before release. The protected historical
PID set is rejected before pidfd or signal. No historical PID/proc lookup or
authority operation is included. The financial interpreter is a timeout/taskset
prefix child, not a production worker; all descendants belong to this new scope.

Proposed bounds: CPU1; target native timeout45s; target plus drain/classification
50s; concrete caller75s from its initial monotonic start including source checks,
plus at most2s wait/.2s drain for failure cleanup. Caller source Git checks use
the remaining global budget. The caller checks that budget immediately before
gate release; cleanup signals use only its held pidfd within the cleanup window.
Late EOF/reap, or any cleanup, cannot restore timely completion. The root must
separately observe the caller's actual exit and EOF; the caller does not certify
its own future exit. Blocking kernel/fsync behavior is not a hard real-time
guarantee: late/incomplete evidence remains UNKNOWN and no retry is automatic.

Shared inner stdout/stderr limit is256KiB including a reserved512-byte trailer;
reserve precedes each sole FD write and short/error/oversize writes are sticky.
Caller stdout/stderr payload limit is1024 bytes including a512-byte trailer;
normal outer stdout/stderr should be empty. Per-file RLIMIT_FSIZE is4MiB;
logical DB family budget64MiB/45 files, checked at connect and fixture/reopen
boundaries; control budget8MiB including retained capsule/raw reservation and
an inner1MiB reservation; caller control64KiB. The aggregate disk check is an
observation, not a continuous native aggregate quota. The nine exact DB families
and their empty private publication temporaries are the only writable authority
paths. No probe may open another authority. First FAIL/UNKNOWN stops subsequent
SQL oracle work, preserves DBs/stdout/stderr/intent/capsule and never refreshes,
retries, rewrites or backdates evidence.

The final plan pins all64 original UTA sources, original test, new oracle,
manual JSON, controller and contract. Caller bytes and exact retained bootstrap
argv have a separate plan; the metadata commit is distinct from its source
origin. Root must approve the final immutable hashes and literal invocation
before any execution. Invocation placeholders are not permission to execute.

## Private originals, deployment and rollback

Use two distinct, nonexistent canonical `/workspace` directories, mode0700;
new files0600/O_EXCL/O_NOFOLLOW. All DB/WAL/SHM bytes, retained full source capsule,
claim nonces, full customer snapshots, concrete birth/PID bindings and raw
stdout stay private. Seal originals and original failures before deriving any
public export. A separate reviewed SAFE export can publish finite checked
booleans, counts, hashes, cleared error excerpts and source/plan SHA only.
Do not publish full captures or commit private payloads.

There is no schema migration, worker activation or deployable production change
in this ENTRY. Deployment is fresh synthetic local authority only after the
separate GO. Rollback stops explicit calls and preserves tasks, unpaid
obligations, cuts, commands, receipts, ledger and original evidence. It must not
delete capability tables or install the old prototype over new data.

All fixtures use an explicit synthetic reference clock. APPLIED is not evidence
of crossing MM, insolvency, loan-only balances, persistent partial-store fault
recovery, network response loss, commit/crash durability, scheduler correctness,
HA, old-binary exclusion, pending-funding admission/withdrawal reserves or
capacity. Those gates remain OPEN and production/real funds remain NO_GO.
