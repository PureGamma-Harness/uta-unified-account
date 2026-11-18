# Fake path closure correction; no test has run

Independent CODE review found a blocking dependency in the unrun9596 six-method
fixture: it supplied `PurePosixPath` to the actual nested audit function, which
calls `.absolute()`. PurePosixPath has no such method; the intended outside-write
RuntimeError would instead be masked by AttributeError. This is a test fake
dependency error, not a production probe-path failure. No batch was executed
to discover or reproduce it.

Source `c076b0dc1feb765686de9c78683a4e4bea5429e2` changes only that test file:
`AbsoluteMemoryPath` implements the required operation for the fixture's
already absolute paths using pure lexical object operations and no I/O. The
actual outside-write audit and production probe are unchanged. The execute
path fake derives from the same memory path. No broad exception is added.
Fixture SHA256 is
`65508ce14d0cab5667ceb7d8a3551627694748676adf25de459d20a34795a443`.
The probe still has SHA256
`4624f4cd5181d5ef526f60cb6c2b126421eace16741537d7a021775397a12bcc`.

The new source-budget is under
`evidence/observer-compact-report-v2/stdin-ownership-c076-preparation/`.
It supersedes executable identities only. The prior source/proposal9596
remains NOT_RUN, the original c9 adapter first FAIL remains unchanged, and all
limitations and bounds from `observer-v2-readonly-stdin-candidate.md` apply.
Proposed next actual adapter path, only after a separate explicit root GO, is
`/workspace/uta-observer-v2-adapter-runs/read1-c076b0d-once02`.

Six focused fake methods are still only proposed for one new CPU1/KILL10s
batch; actual adapter execution requires a distinct later authorization.
Neither is authorized by this document. No test, real pipe/child, null-device
read, SQL, watch, network, crypto, CI or long run was executed for this fix.
Rollback is to retain the unrun sources/evidence and omit this fixture-only
candidate; legacy remains the default. No data migration is introduced.
