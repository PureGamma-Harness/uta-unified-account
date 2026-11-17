# Public frame header ownership correction

The prior unused pure prototype `c7bbd41` retained a bytearray passed directly
as the public WireFrame constructor's header when its initial content equalled
the expected header. A normal external alias could then change wire opcode
bytes while the frame's declared opcode remained unchanged. The ordinary
encode factories already supplied immutable bytes; this is a public-constructor
ownership defect in the new unused component, not a live gateway or financial
route finding.

The exact before runtime/tests and SHA map, actual 28-case/1-FAIL log, and pure
alias observation remain here. The observed wire changed from `810178` to
`820178` while declared opcode stayed 1. No SQL, socket or service was used.

Fix source **24337ede7b07083c13c16736cb78628d6a01a7ec** rejects a header unless
its exact type is immutable bytes before validating the contents. It adds two
runtime lines and one six-line test; previous runtime/test source and results
are unchanged in their separate worktree and archive. Fresh exact-source runs
passed 28 cases on Python 3.10.22, 3.12.14 and 3.13.5 sequentially on CPU 3,
ResourceWarning treated as error, in .006/.005/.004 unit seconds. Original logs,
actual UTC/argv, hashes and clean/unchanged source checks are under
`final-24337ed`.

This report adds evidence only; it does not change the tested code. Component
correctness still needs independent peer review. No full repository, package,
network scheduler/RTO, auth-session, reader, listener, capacity, long-run or
production approval is supplied. Rollback removes only the unused new library
and associated tests/docs; it does not touch balances, nonce stores, account
cursors, authorities or any running source.
