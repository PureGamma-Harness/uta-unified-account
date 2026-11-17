# Final fixed ABBA16 diagnosis bindings (execution pending)

This is the bound successor to the earlier proposed preregistration, using root's
selected policy: ordinary original assertion FAIL is retained and the fixed
remaining sequence continues **only if every technical gate passes**. ERROR,
unknown evidence, observer failure, timeout, forced cleanup, residual process,
source or runtime mismatch stops the remaining slots. The original single run
in b570 and the original 8f strict-gate defect plus independent four-vector red
in 8285 remain unchanged. This revision supplies a new strict helper and pure
record validator; it does not relabel any past outcome.

The immutable machine-readable registration is
`evidence/runs/recovery-horizon91/runtime-ab16-preregistration.json`.
It fixes 16 samples as ABBA repeated four times, CPU2, one original exact91 case
per fresh directory/session, unchanged 5/5/5/5/15 original limits, 27-second worker
watchdog and a 30-second whole sample including capability/source preflight and
cleanup. The controller reserves the last 0.75 seconds for bounded cleanup and
final evidence; an outer reserve expiry is technical NO_GO, never a change to a
successful original recovery assertion or an excuse to expand its deadline.
There is no sample retry or extra warmup case. Unexecuted slots remain present
as NOT_RUN_DUE_TO_SAFETY_STOP. All completed and failed raw outputs are retained.

A is `/usr/bin/python3.13`, expected 3.13.5 / SQLite3.46.1, executable SHA
889c603f0d17cb54060951bcf4c4f9b8c9ebd9e52b392c70209bbb9755d797d9.
Its ELF NEEDED entries do not include libpython: the Python core is embedded in
the executable. The separately installed system libpython SHA is pinned as an
available but unmapped file; the child must observe no mapped libpython.
B is `/tmp/uta-python31318-24-20261117/runtime/bin/python3.13`, expected 3.13.18 /
SQLite3.46.1, official actions/python-versions build from preparation commit
98e802f6cb0c2c692bd3dfa70c91a346d87cdfc6. The exact provider archive, executable
and prefix libpython hashes are pinned in the JSON. B maps its own prefix
libpython via process-local LD_LIBRARY_PATH. It uses GCC13.3.0 on this host,
whereas the failed CI runtime used GCC15.2.0 and a different image/kernel/libc.
This does not recreate the full CI environment or establish version-only cause.
The initial B executable's wrong3.13.5 loading evidence remains preserved in98e.

Both environments explicitly remove PYTHONPATH/PYTHONHOME, Python startup,
inspection, optimization, safe-path and hash-seed overrides, and LD_PRELOAD.
A also removes LD_LIBRARY_PATH; B sets it to its fixed prefix library directory.
Both set PYTHONDONTWRITEBYTECODE=1. No global environment or other job is changed.
For each sample, a plain child process in its actual environment reports its
version, executable, SQLite version, flags, compiler/platform/libc, mapped
libraries and hashes, provider/binary/libpython hashes, and all 266 original
source hashes. This preflight opens no SQL connection and does not start the
case. A mismatch stops before a financial testcase begins.

The new `trace_original91_strict.py` records exact observer lifecycle and
post-join state. The pure `strict_result_contract.py` rejects string or numeric
booleans, bool-valued counts, missing fields, skipped/non-single cases, inconsistent
was_successful/case_passed/counts/historical-stage facts, and inconsistent observer
aggregates. `run_runtime_ab16.py` revalidates the result and raw unittest footer,
original assertion text, event hash, exact launcher booleans, original source
maps, actual runtime, and fresh-session cleanup. Its positive aggregate cannot
be accepted from a truthy JSON value. PID signals are restricted to retained
pidfds or original logged child births; a bare reused SID is not kill authority.
Unknown unrecorded residuals are recorded and escalated rather than signaled.

The proposed invocation after separate exact root GO is:

```
umask 077
env -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH -u LD_PRELOAD \
  PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3.13 -B \
  evidence/runs/recovery-horizon91/run_runtime_ab16.py --run NEW_PRIVATE_OUTPUT
```

The controller has no default action. Root and an independent reviewer must
approve exact helper, validator, probe, controller and registration hashes before
it runs; source/preparation capability evidence alone does not grant execution.
No new financial native case was executed while authoring this plan.

This batch diagnoses causality only. Sixteen passing cases mean NO_REPRO under
these bindings; the old CI failure and source91 NO_GO remain unresolved. Any
captured failure is reported by original stage with monitor/status/PID evidence;
there is no unreviewed runtime fix, source91 qualification or production approval.
Stopping use of this optional controller is the rollback; it changes no schema,
production default or global runtime. Preserve all original and later raw files.
