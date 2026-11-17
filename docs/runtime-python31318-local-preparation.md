# Local Python 3.13.18 preparation

The official Ubuntu24.04 x64 Python3.13.18 archive is prepared for **future,
separately authorized diagnosis**. This preparation ran no SQL connection,
financial test, service, old-job status command or signal. It is not a rerun
or resolution of the original91e CI recovery failure.

The official `actions/python-versions` manifest and release metadata were read
through the GitHub connector. Release `3.13.18-40336726450`, asset678421609,
has102,778,317 bytes and SHA-256
`683005a1465d94d40045f6a1a6eb316885b5f08d3360f7922b44ef58a14a9eed`.
The downloaded original matches both. Its9,345 members were checked for path
traversal, escaping links, special files and setuid/setgid bits before extraction
into a fresh0700 directory. Eight links are relative and internal. Neither
`install.sh` nor any global installer was executed. Original archive and derived
prefix stay outside Git.

The executable is
`/tmp/uta-python31318-24-20261117/runtime/bin/python3.13`.
It requires this process-local environment:

```sh
env -u PYTHONPATH -u PYTHONHOME \
  LD_LIBRARY_PATH=/tmp/uta-python31318-24-20261117/runtime/lib \
  PYTHONDONTWRITEBYTECODE=1 \
  /tmp/uta-python31318-24-20261117/runtime/bin/python3.13 --version
```

Do not silently omit the library setting. The initial command without it
returned exit0 but loaded the system3.13.5 `libpython`; the strict expected-version
assertion failed. The initial version/capability stdout, unchanged original
preparation driver and failure record are retained. This was a preparation
environment error, not evidence about the trading system. Only the later
local-library check establishes3.13.18 availability; the earlier failure is
not relabeled.

The final read-only verifier checks the exact extracted executable and
`libpython` against their archive members, observes the actual mapped libraries,
and requires both parent and plain child `--version` to report3.13.18. It
imports SQLite only to read its version, without opening a connection. The
command and actual stdout/stderr are retained in
`evidence/runtime/python31318-24/`.

| Field | Prepared local runtime | Original failing CI runtime |
| --- | --- | --- |
| Python | 3.13.18 | 3.13.18 |
| Compiler | GCC13.3.0 | GCC15.2.0 |
| libc | glibc2.41 | glibc2.43 |
| Kernel | Linux6.18.57 | Linux7.0.0-1019-azure |
| SQLite version | 3.46.1 | 3.46.1 |

This is a different platform build and host, not the same CI binary or complete
CI environment. The executable maps its own prefix's `libpython` but the host's
SQLite/OpenSSL libraries; final output identifies their paths and OpenSSL3.5.7.
Equal SQLite version strings do not establish equal build options or all
dependency bytes. No defect fix, recovery timing, full qualification or
production approval follows from these capability checks.

The archive plus derived prefix contain433,724,195 logical regular-file bytes.
Final observed filesystem free space was18,289,790,976 bytes; it is a timestamped
shared-host observation, not a reservation. Future experiments must include
the environment above, fixed source and driver identities, their own explicit
budgets and original output directories. Do not replace an earlier experiment's
interpreter or environment and relabel its result.

## Rebuild and rollback

The first preparation script is historical and intentionally refuses an existing
prefix; it also preserves the initial version-assertion failure. The final
`verify_prepared.py` is the current read-only capability verifier, not an
authorization to run financial cases. Rebuild in a new private directory from
the retained, hash-verified official archive, validate all members again and use
the local library setting. Never execute the bundled global install script.

This evidence-only change has no schema or deployment migration. Existing
Python runtimes, global PATH/libraries and original jobs were unchanged.
Rollback can stop using this optional prefix; keep the original archive and
all first-failure/capability evidence. No original frozen source or experiment
needs alteration.
