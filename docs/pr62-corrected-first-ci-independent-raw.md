# PR62 corrected first CI: independent RAW review

Status: **retained evidence reproduced; suite FAIL; release qualification null**.
This documentation-only review authorizes no deployment or target execution.

The collector is `d4208f8044939759efcab10d28a4258de3f8de15`, with exact parent
source `8faa56d5fcfcd1b176cbb1c2d8e142986f56ab15` (C). The fixed sample is first
attempt push run `44342181511` and PR run `44342194604`. Earlier first-CI
originals and reviews remain untouched. No later correction, rerun, replacement
job or green artifact contributes to this review.

## Integrity and finite privacy checks

The independent reader checked the exact 36 sealed originals, totaling 2,448,301
bytes, against the separate private index. All files remain regular mode `0400`;
all seven directories remain `0500`. Initial and final hash/size/mode checks
passed. The private index SHA256 is
`ac22909693514b17630dfc02ff673337c7923dd4cdcf023eee8f1ce8fae365b3`.
The public review contains opaque IDs, byte counts and hashes, without private
original names, actual runtime identities, download references or raw log bodies.

All thirteen collector SAFE files match their immutable Git blobs, and its
twelve-entry inventory with self-exclusion is consistent. The collector helper
was read as source/AST only, never imported or executed. Six strong actual
download/runtime values extracted from the retained data had zero matches in
the collector SAFE projection. This finite negative check does not establish
unrestricted privacy coverage.

Three selected unit ZIPs have nine unique members. All nine CRCs and member
hashes/lengths match sealed extracted copies. The independent read ledger records
**nine member reads, zero repeat reads and 1,551,656 expanded bytes**. Compressed
originals total 323,905 bytes. Member reads were bounded before expansion by a
1 MiB per-member limit and an 8 MiB aggregate limit; there was no extraction,
archive mutation or release-reader execution. Collector and independent read
counters are separate scopes even though their counts agree.

## Source and provider identity

All 410 unique unit source-map entries and all 66 runtime files match C's Git
blobs, byte counts and SHA256. Three complete summaries' before/after maps give
six maps and 2,460 tuple comparisons. Runtime is 65 Python files plus one HTML,
totaling 1,470,877 bytes. The explicit test inventory V3 was resolved by bounded
AST/literal inspection and contains those exact 65 Python paths.

C has 7,831 tracked files totaling 223,881,633 bytes by Git metadata. Runtime,
tools, benchmarks and workflow bytes are unchanged from prior source72dd; four
test/fixture files differ. Three runtime paths differ from base
`ef7508bebd35cac71d9db8fdda896806ce4ade64`; the remaining 63 are unchanged.

Retained provider metadata identifies merge
`6e33df120cbd6b7b79b24c0b837728be722c6253`, with parents base and C. Its tree
equals C's local tree `58704fdb7d95e5c4e9449e9a888b0cf4297e46c3`. The merge
commit object is unavailable locally; provider metadata and local object
availability remain distinct. No network fetch was attempted. Source identity
does not qualify an installed package.

## Actual ordinary CI observations

Both runs are completed first-attempt failures. Eight jobs contain 200 steps:
64 success, eight failure and 128 skipped. Every failed step is `Run unit tests`.
All eight original job texts report 2,193 tests, two failures, zero errors,
zero skips and worker exit 1. Aggregate job JSON does not establish eight full
per-method archives.

Complete selected logs were independently checked for fixed push Python 3.13,
fixed PR Python 3.13, and the explicitly additional first-failed push Python 3.12
diagnostic. Strict same-line `plain-ok` counts are 2,162 for fixed push and 2,163
for fixed PR; neither equals the reported 2,193 tests. All 22 distinct new methods
have one strict same-line `ok` in each fixed archive: **44 fixed observations**.
The additional Python 3.12 record is separate. No method result is extrapolated
to the other six jobs, custom pure5/SQL17 receipt capture or installed execution.
Custom component receipt capture remains NOT_RUN.

The earlier four failing methods have these bounded observations in each fixed
archive:

| Method scope | Actual completion syntax |
| --- | --- |
| Readiness incomplete-watermark/control flags | Strict same-line plain `ok` |
| Partial-publication command handling | Strict same-line plain `ok` |
| Exact-original-source/code-object capture validation | Strict same-line plain `ok` |
| Native shared-gate capture horizon | Diagnostic on the method line, then standalone `ok` before the next method: **INTERLEAVED_METHOD_COMPLETION_OK**, not same-line plain `ok` |

These observations do not retroactively resolve an earlier historical failure.
The private interleaved diagnostic remains private. The selected corrected logs
record the following two failures in all three complete archives:

| Test | Exact source frame | Recorded failing check |
| --- | --- | --- |
| `FailureDiagnosticTests.test_complete_original_ast_is_preserved_except_exact_failure_hook` | `tests/test_expired_gate_failure_evidence.py:119` | Whole-module canonical AST comparison after the specified hook removals |
| `NativeSHCaptureProtocolPureTests.test_capture_failure_is_one_shot_and_original_recovery_ast_is_untouched` | `tests/test_native_sh_capture_protocol_pure.py:205` | Invocation of the retained guard as `ActualASTGuard`, failing the same comparison |

Both assertions record actual AST SHA256
`0b20c601d3d20df91537154703257db3258ad58feec0bf286735d927ce7d9fdc`
and expected
`6158b76f0c38eb9aa7acf7a4c28c88357cb3223a0f875bcb63f2db08b513b1d6`.
The expected value matches C's retained `original-ast.json` Git blob. Failure
frames were checked against enclosing source methods. The guard was not run or
reimplemented by this reviewer; actual is a recorded assertion value, not a
newly calculated result. Exclusive root cause remains
**UNDETERMINED_BEYOND_RECORDED_ASSERTION**. No later AST delta is used here.

## Package and administrative limits

Both terminal artifact inventories contain only four unit archives each. Fixed
push Python 3.13 package/release reports and wheel/sdist are NOT_AVAILABLE.
RECORD, release source identity, installed behavior, funding3/candidate/oracle
direct installed coverage remain NOT_VERIFIED. The static archive-audit draft
was NOT_EXECUTED and is not a budget qualification. Release outer expansion,
wheel content, complete gzip/tar stream and visible sdist payload counters all
remain zero. No alternate artifact was substituted; release qualification is null.

The collector records no administrative correction in this scope. The first
independent retained-data reader completed without a schema correction or
repeated ZIP read. Public report status wording was finalized after that successful
read; this was a documentation update. No target, CI or provider operation was
retried. Reading source that contains executable helpers does not mean those
helpers were invoked.

## Delivery and rollback

The companion is
`evidence/reviews/pr62-corrected-first-ci-independent-raw/review.json`.
Only these two review files are new. Original data and all thirteen collector
files remain unchanged. Rollback is a revert of this documentation-only commit;
there is no runtime deployment, data migration or financial state transition.
No target import, compilation, test, SQL, process/PID lookup, worker, clock,
native actor, CI rerun or network access was performed. No financial, sustained
10,000/s, duration, HA, production, installed-package or real-funds gate closes.
