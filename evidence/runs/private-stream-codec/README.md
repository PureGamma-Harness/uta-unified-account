# Pure private-stream codec evidence

Fixed runtime source: `c7bbd41f1e4ea48961a59921826f80c585c34e6d`.
The exact clean source ran **27 pure component tests** on CPython 3.10.22,
3.12.14 and 3.13.5, sequentially pinned to CPU 3, with ResourceWarning treated
as an error. Original logs and exact UTC/argv/runtime/input hashes are retained
under `final-c7bbd41`; unit times were .005/.004/.007 seconds. Source stayed
unchanged and clean. The host was cohosted, not dedicated capacity hardware.

These tests execute bytes, integer arithmetic and caller-supplied model times.
They open no auth/financial database or socket, start no server/worker, and do
not access any running job. No real scheduler/revocation/network deadline,
full repository, installed package, performance, long-run or production result
follows. Existing gateway/auth/view/financial modules were unchanged.

Original development results remain separate:

- `initial-missing-codec.txt`: the tests-only commit `7ff78ce` correctly failed
  import because the module did not yet exist; `initial-frozen-tests.py` is that
  exact committed test source. This is not an existing exchange runtime failure.
- `first-implementation-py312.txt`: 22 initial tests passed. Runtime was then an
  uncommitted development file, whose bytes equal the preserved
  `closing-ownership-before-runtime.py`; test bytes were the tests-only commit.
  It is not reported as clean frozen qualification.
- `closing-ownership-before.txt`: three additional requirements exposed
  1 FAIL and 2 ERROR for mutable payload backing and absent full-queue/closing
  deadline interfaces. Both exact input files and SHA map are retained. The
  following 25-case result is separately `closing-ownership-after.txt`.
- `output-token-before.txt`: two further actual failures exposed a forged
  partial-output token accepted by the draft and overridable text encoding.
  Exact before sources and SHA map remain. `output-token-after.txt` records
  the corrected 27-case development result, before final commit qualification.

The runtime uses immutable payload backing, exact most-recent partial-output
identity, type/length checks before encoding, and an absolute close deadline.
No historical failed log, source, business result or active job was rewritten.
Reference fixtures and RFC/IANA records are in the two design commits; their
other permission/nonce/snapshot requirements remain NOT_RUN_REQUIREMENT.

Reproduce the small suite from a new checkout of the exact source commit:
`taskset -c 3 <python> -W error::ResourceWarning -m unittest discover -s tests -p test_private_stream_codec.py -v`.
Choose an allowed CPU on other hosts and record that actual configuration.
The report commit adds evidence only. Code review remains an independent gate
before any bounded-reader, auth-session or listener slice. Rollback removes
only the unused new library/tests/docs; no financial or authentication data
migration or rollback is involved.
