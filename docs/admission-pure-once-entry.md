# Seven-method admission pure once: CODE proposal

Status: NOT_RUN, zero target attempts. Root execution GO and independent
entrypoint CODE review are required. The existing financial/test source is
`be3c5c3ad695caedf438e09a25461571855fc43d`; its fresh-preparation delta was
independently reviewed at `071e761fe330c770a0fcffaac6cae5e1d5446a5c`.
That review does not authorize this new execution entrypoint.

## Retained source and fixed selection

`tools/run_admission_pure_once.py` derives its parent capture, retained
bootstrap, raw budget and terminal publication from funding pure source
`7ebd8f5fa17d4c339956bbe4e5f04a529d83a8a4`, driver SHA-256
`5bf9033c85ecdcfdce4f73dccd6536a767347c365a3a81926b3839f45d271a42`.
The `FrozenUTA`/`FrozenLoader` mechanism follows the funding SQL loader and
imports complete modules from the retained input map. No UTA or test AST is
extracted, rewritten or compiled during this CODE preparation. At a future
authorized execution, ordinary Python import semantics operate on the full
retained source, including original decorators, annotations and descriptors.

The closure contains all61 UTA Python sources, the unchanged seven-method pure
test file, this entry document and the once driver. The plan itself is bound
separately by its approved SHA and exact Git/physical bytes; it cannot contain
its own content hash recursively. All declared source bytes must also equal
the approved final invocation commit. A separately retained manifest records
their origin commits and hashes. The current full seven-pure/four-SQL plan
and the original90ba plans are preserved byte-for-byte. The four-SQL test file
is not in this new retained input map and is never selected or compiled.

Only `AdmissionPolicyReferenceTests` and its seven literal method names are
instantiated directly. There is no discovery or SQL/native mode. All financial
and both original test files remain byte-identical to be3c5c3; only this control,
documentation and new metadata are added. Risk and reserve valuation still use
the existing `_replay_state` engine, so these cases are not an independent
Cross valuation model. Their expected financial constants and supported replay
predicates retain the previously reviewed scope.

The expected loaded UTA modules are the static eleven-module import closure:
`uta`, `decision_audit`, `ledger`, `market`, `models`, `portfolio`, `products`,
`reserve_kernel`, `risk`, `scenario_margin`, `storage` (all names except `uta`
have the `uta.` prefix). All other retained UTA modules remain unexecuted.
A different loaded set fails this limited qualification. Importing the
SQLite library is permitted; a `sqlite3.connect` audit event is denied.

## Resources and completion

The outer controller creates one new exclusive0700 namespace with0600 files.
It validates the actual Git HEAD, physical regular-file SHA/lengths and plan,
then stores a private retained capsule. Only one owned timeout/taskset target
interpreter is launched, with pinned Python3.12.14, `-I -S -B` and CPU affinity
`[1]`. Read-only Git/source preparation is outside the ten-second target
interval and is not a test warm-up. No result from it is a business success.

The target has GNU `timeout --signal=KILL 10s`; the outer target/drain
classification deadline is12 seconds from target launch. Native blocked I/O,
parent preparation and final fsync are not preempted by that Python deadline.
The caller must separately observe the actual outer exit, reap and monotonic
end; an inner receipt or proposed return code cannot prove a future exit.

Both target stdout/stderr enter parent-owned pipes, including bootstrap,
Python/native FD writes, taskset and timeout output. One counter reserves bytes
before writing either raw file:32768 shared bytes, including a512-byte terminal
trailer. Overflow or short write is sticky UNKNOWN/125, with no later payload
or retry. The inner has no child/thread/SQL/network/proc/signal permission:
reviewed fixed tests plus an audit hook deny connection, process, socket and
authority/proc operations; thread-start entrypoints are denied. These are
trusted fixed-source guards, not an OS sandbox against hostile native code.

The logical control envelope is8MiB, with1MiB reserved for the two fixed inner
control files and32768 bytes for target raw output. Every control-file creation
is exclusive and charges its bytes; retained files are individually at most4MiB.
There is no database or database sidecar. This is logical accounting for the
reviewed fixed paths, not a filesystem hard quota or an unrestricted disk claim.

Limited PASS requires seven actual tests with no failure/error/skip/EF/US,
unchanged inputs/plan, the exact runtime/loaded modules, zero forbidden attempts,
matching original BEGIN/END and inner receipt, both raw pipe EOFs, actual owned
target exit0/reap, nonsticky capped raw streams and a timely final TAIL. Source
or timing drift is UNKNOWN. A failed seven-test suite can be a complete FAIL;
missing/incomplete evidence is UNKNOWN. First FAIL or UNKNOWN is retained and
stops the scope; no warm-up, quote refresh, changed selector or retry follows.

## Caller protocol to review before GO

The root caller owns a new separate0700 namespace and the outer `Popen`
handle. It must freeze the literal argv below, exact source commit, plan SHA,
runtime and its own launch source/intent before execution. It records actual
monotonic start/end, actual return/reap and stdout/stderr EOF independently.
Outer-controller launcher streams are expected empty; any nonempty/overflowing
launcher output needs preserved capped evidence and cannot be silently excluded
from an aggregate raw acceptance claim. Count it alongside target raw output;
aggregate overflow is UNKNOWN. The caller must bound its capture and retain the
first error. It must not inspect or signal any old PID, infer completion from
END, overwrite a namespace, delete evidence or retry this business scope.

```text
<PINNED_PYTHON312> -I -S -B <ROOT>/tools/run_admission_pure_once.py
  --execute --source-commit <APPROVED_FINAL_COMMIT>
  --plan-sha256 <APPROVED_PURE_PLAN_SHA256>
  --output /workspace/<NEW_EXCLUSIVE_PRIVATE_ONCE_NAMESPACE>
```

The reviewed outer entry is executable code. The external caller is a separate
observation boundary; this document does not fabricate a caller exit record.
Root must bind its concrete bounded caller before GO. Pure execution grants no
SQL, actual service order, matching, worker, performance or production approval.

## Privacy, deployment and rollback

Retained full source capsules, complete controls and any process bindings stay
private. Publish only independently cleared finite synthetic fields and hashes.
No runtime, schema, API or account mutation is introduced by this tooling.
Keep audit activation restricted to fresh synthetic authorities as documented
in `admission-decision-replay.md`; existing-authority migration remains OPEN.
Reverting the new entry/plan/document restores the prior preparation state and
preserves every original review and first-run record. No database rollback,
policy deletion, artifact weakening or real-funds activation is authorized.
