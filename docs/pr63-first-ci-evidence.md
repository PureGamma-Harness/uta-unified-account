# PR63: first normal CI evidence

Fixed source **16f64fec1d2fba638ea99a6414cf8778f9638537**. First push
**44353030187** failed; first PR **44353143243** succeeded. Both are attempt 1;
there was no workflow rerun or replacement. The source is not accepted as wholly
green. Across eight jobs, seven succeeded and the push Python 3.12 unit step
failed. The 200 steps contain 183 successes, one failure and 16 skipped steps.

All eight original job summaries report 2,200 tests. Seven report zero failures,
errors and skips; push Python 3.12 reports one failure, zero errors/skips and
worker exit 1. The full failed unit artifact identifies
`test_process_readiness.ProcessReadinessTests.test_same_version_changed_persistent_content_is_not_reused`,
with an AssertionError at tests/test_process_readiness.py:200. Its full original
traceback is retained privately. The finite public projection does not establish
the cause; **UNDETERMINED** remains the recorded classification.

The two predetermined Python 3.13 unit artifacts and the uniquely added first
failed Python 3.12 artifact each retain 410 source hashes before and after tests,
identical to fixed Git bytes. Those three complete logs each show all 29 funding
methods as strict same-line plain-ok: 87 method observations, not 87 distinct
methods, not a subtest callback count, and not individual transcripts for the
other five jobs. Complete-log plain-ok counts are respectively 2,172, 2,172 and
2,171; these are not the 2,200-test summary totals.

Runtime is 66 Python files plus one HTML file, 1,479,474 bytes. Explicit V4
matches the current Git Python set; historical V2=62 and V3=65 remain intact.
The PR provider merge 574e82298ba49dd5e38d1f2e0ecda402fb49ebd6 has parents
public ef7508be and source16f64, with the same source tree871e55bed70aca4db42f5405c3556fefac8bacdd.
Its local commit object was absent; provider metadata and fixed source hashes
are separate evidence, not a claimed local merge-object verification.

## Package evidence and its limits

The fixed push Python 3.13 small package artifact reports matching 67 runtime
hashes, the exact 7,844 required Git paths, and an unchanged CLI helper. Its
installed report records eight tests with zero failure/error/skip, eight
commands returning zero, 25 loaded module names and isolated execution. The
reported module list excludes funding_local, funding_obligations,
perpetual_funding and funding_hold_pure. This does not establish direct installed
functionality for the funding components or the independent oracle.

Exactly one actual binary ZIP was retained: artifact14449947051, 54,814,960 bytes,
SHA256 dd18f8b204f1a76e9454fd5d3d4456f8736352d2ef27b276431fb6d753bc591c,
matching provider metadata. Only its two-entry outer central metadata was
inspected. Its members were not opened for payload or CRC, and wheel/raw-tar
payload reads are zero. Binary qualification is **null / NOT_VERIFIED**. Producer
package reports do not substitute for independent validation of the binaries.

Four small ZIPs produced 28 complete CRC-verified member reads with no repeated
archive expansion, totaling 2,226,064 bytes under the shared 8 MiB bound. All
compressed hash scans, repeated decoded parsing and the limited scope of those
metrics are disclosed separately; they are not a physical I/O quota or deadline
proof. The original 128 MiB/256-file retention budget remains unchanged.

## Provenance, deployment and rollback

64 original files, 75,584,560 bytes, are sealed mode0400 in ten mode0500
directories. The private name-bearing index SHA256 is
19263b85f6c1c000717b74f2cb62b35d29338250912ff95e8e9b61da916226f5.
Public files contain finite opaque inventories, source bindings and projections;
original signed download references, runtime paths and raw traces stay private.

The stable d420 reader was copied with SOURCE/tree literals rebound, then a new
immutable copy changed only the testcase-path tuple from the old two market
files to the actual funding test file. The original reader is retained privately;
all other AST nodes are unchanged for this necessary component delta, approved
by root before invoking it. It imports no UTA or target test code. Collector
operations are source/AST/JSON/ZIP/Git data operations; no local target import,
compilation, test, SQL, native actor, process/PID inspection or financial action
was performed. CI execution is recorded separately from collector execution.

This delivery adds evidence only. There is no deployment, account migration or
capability activation. Reproduce against the fixed source and preserve this
first failure; a later correction needs a separate source and first-run scope.
Rollback reverts only these evidence files and never deletes or rewrites the
sealed originals, confirmed obligations, trades, positions or journals.
Independent RAW review is pending. Reference differential tests, D2 integration,
HA, sustained capacity, production and real funds remain unqualified.
