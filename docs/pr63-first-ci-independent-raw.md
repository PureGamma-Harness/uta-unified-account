# PR63 first CI: independent RAW review

Status: **evidence reproduced; first push FAIL, first PR SUCCESS; source is not
wholly green; release qualification null**. Collector
`6cd4c01d63007e6d51025f2a37c28bf52aeb0764` has exact parent/source
`16f64fec1d2fba638ea99a6414cf8778f9638537` (C). No target/reference import,
compilation, test, SQL, proc/PID inspection, actor, network or CI operation was
performed. No subagent was started.

## First results and source bindings

The retained originals show both fixed runs bound while in progress, attempt 1:
push `44353030187` later failed; PR `44353143243` succeeded. All terminal job
metadata and eight original job-log summaries agree. There are seven successful
jobs and one failure; 200 steps comprise **183 success, one failure, 16 skipped**.
Each summary reports 2,200 tests. The failed push Python 3.12 job
`134973560798` reports one failure and worker exit 1; the other seven report zero
failures and worker exit 0. All report zero errors/skips and unchanged, clean
source. Original Python-version/source fields associate each summary with its
exact event and matrix job. The PR success does not replace the first push.

The fixed push/PR Python 3.13 archives and the uniquely added first-failed push
Python 3.12 archive contain complete unit logs. Each has all 29 funding methods
as strict same-line `ok`: **87 observations of 29 distinct methods**. These are
not 87 distinct methods, subtest callbacks, or complete per-method records for
the other five jobs. Whole-log strict plain-ok counts are 2,172, 2,172 and 2,171,
separate from the 2,200-test summaries. Independent reference/differential receipt
qualification remains NOT_RUN.

All 410 unique source entries match C's Git bytes, SHA256 and blob IDs. Three
before/after pairs give six maps and **2,460 tuple comparisons**. Runtime is
67 files, 66 Python plus one HTML, totaling 1,479,474 bytes. Static AST resolution
confirms historical V2=62, V3=65 and current V4=66, with V4 equal to the exact
current Git Python paths. C has 7,844 tracked paths and 224,018,488 tracked bytes.

Retained provider merge `574e82298ba49dd5e38d1f2e0ecda402fb49ebd6` has parents
base `ef7508bebd35cac71d9db8fdda896806ce4ade64` and C. Its tree equals C's
`871e55bed70aca4db42f5405c3556fefac8bacdd`. The local merge object is absent;
provider metadata and local object availability remain separate facts. Source
pins do not attest installed binary contents.

## The preserved first failure

The sole recorded failure is
`ProcessReadinessTests.test_same_version_changed_persistent_content_is_not_reused`
at `tests/test_process_readiness.py:200`: final `financial_ready` is false at an
`assertTrue`, recorded as `AssertionError: False is not true`.

The source reaches that assertion after activation calls at lines 191 and 199.
The `activate` helper at line 110 calls `wait_ready` at line 118 before returning.
This verifies earlier source/control-flow progress, not contemporaneous evidence
about the later `financial_ready` value. The selected summary has zero lease
observations and no diagnostic record establishing this failure's cause.
**UNDETERMINED** remains the classification. No native process was re-executed,
no single cause was assembled from separate observations, and no readiness
threshold or financial gate was relaxed.

## Integrity and read accounting

All **64 originals / 75,584,560 bytes** were independently hashed once and match
the sealed private index SHA256
`19263b85f6c1c000717b74f2cb62b35d29338250912ff95e8e9b61da916226f5`.
They remain regular mode `0400`, in ten directories mode `0500`. A final exact
file-set/size/mode check followed; it is not presented as a second content hash.
All thirteen collector SAFE files match collector Git bytes and its twelve-entry
inventory with self-exclusion. The name-bearing index and originals stay private.

The pre-read plan was fixed before original reads. Before any raw file or ZIP
open, v2 added only a private nonbinary cache allowance, 32 MiB retention and
64 MiB input including repeats; existing layer caps were unchanged. This keeps
schema refinement from rehashing the large binary or re-expanding members.
Native list/dictionary types were checked before iterating the read ledgers.

Four small ZIPs have **28 unique member reads, zero repeated member reads and
2,226,064 expanded bytes**, all CRC/hash/length matched to sealed extracted
copies. Non-ZIP originals contributed 20,380,080 hash-input bytes; small ZIP
whole-file hashes contributed 389,520 bytes. Separately charged small central
metadata was 2,524 bytes, and small compressed input including whole hashes and
in-memory member reads was 776,148 bytes. These stay distinct from expansion.

The one binary ZIP, artifact `14449947051`, is 54,814,960 bytes with outer SHA256
`dd18f8b204f1a76e9454fd5d3d4456f8736352d2ef27b276431fb6d753bc591c`,
matching provider metadata. This reviewer made **one full compressed hash pass**
and read 218 bytes of central metadata for two entries. No binary member was
opened for payload or CRC; wheel and complete gzip/tar-stream reads are zero.
The collector's separate two hash passes and repeated decoded-file parsing are
preserved, not relabeled as this review's counters. No arbitrary physical-I/O
quota, kernel limit or realtime deadline is proved.

## Package reports, finite privacy and administrative corrections

The small package manifest's 67 runtime hashes and 7,844 required paths match C's
runtime bytes and exact tracked path set. Its runtime digest was independently
recalculated as data. The installed report has eight tests with zero failures,
errors/skips and eight commands returning zero; the eight CLI method lines and
three helper hash records agree with retained source/report fields.

Its **25 module values are paths, not content hashes**. The direct list excludes
`funding_local`, `funding_obligations`, `perpetual_funding` and `funding_hold_pure`.
Direct installed funding/pure functionality and independent-oracle functionality
remain NOT_VERIFIED. Binary member names/sizes agree with the reports, but their
actual contents, wheel RECORD and raw-tar stream remain unverified. Reported
producer checks do not substitute for those reads; binary qualification is
**null / NOT_VERIFIED**. No new full-layer helper ran.

The stable d420 helper was independently reconstructed with C/tree literals
rebound. Its further byte/AST delta is exactly the approved replacement of the
two old market-test paths with `tests/test_funding_hold_pure.py`; all other AST
nodes match. This reviewer did not import or execute it.

The collector's 33 actual absolute-path tokens were independently reconstructed
from the installed report using its exact declared rule. All thirteen SAFE files
have zero matches. Five actual signed download references likewise have zero
matches. No token value, runtime path or raw reference is printed or exported.
This finite check is not a universal secret scan or a runtime PID/nonce proof.

Administrative facts are preserved. Two public-only schema probes stopped on
incorrect object assumptions before any raw read. A later optional job-association
probe assumed job IDs occurred in private filenames; the corrected association
used actual Python/source fields from one prebudgeted private cache reread.
A source query initially looked for a direct wait call; the actual relation is
test → activate helper → wait_ready. Repeated source/cache/public reads are
charged separately. None caused an original/ZIP-member, target, provider or CI
retry, and none changes the first failure's classification.

## Delivery and rollback

Only this document and
`evidence/reviews/pr63-first-ci-independent-raw/review.json` are new. Collector
thirteen files and all 64 originals remain unchanged. Rollback is reverting this
documentation-only commit; it performs no deployment, schema/data migration,
capability activation or financial transition. The initial failed scope stays
retained. D2 integration, reference differential qualification, sustained
capacity, HA, production and real-funds gates remain open.
