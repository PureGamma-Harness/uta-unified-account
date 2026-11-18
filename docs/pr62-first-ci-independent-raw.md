# PR62 first CI: independent RAW review

Status: **evidence reproduction accepted; suite FAIL; release qualification null**.
This review adds no runtime change and authorizes no execution or deployment.

The immutable collector is `32427eb1c83a45d36c613acf68d244622fb5360b`, based on
source `72dd3a17d7a8e363d95854ee8c4f361e0a24d901` (C). Only the first attempt of
push run `44336268341` and PR run `44336471937` is in scope. No later compatibility
patch, replacement job, green result, CI rerun, package build, target import,
compilation, SQL, worker, process lookup, or network access was used.

## Integrity and identity

The independent reader checked the exact set of 46 sealed originals, totaling
2,606,723 bytes, against the separately sealed private index. All files remain
regular mode `0400`; all seven directories remain `0500`. The private index SHA256
is `2d8e6a0eafec60909e3100b8228f77ed5deb57f18a0b0794fc55b3e82e5c1a82`.
The report publishes only opaque original IDs, byte counts, hashes and modes.

All 13 collector SAFE files, totaling 226,474 bytes, match their collector Git
blobs. Its twelve-entry inventory and self-exclusion are consistent. Six strong
private runtime/download identity values extracted from retained originals had
zero matches in these SAFE files. This is a finite projection check, not a claim
of unrestricted privacy coverage. The collector helper was inspected as AST and
source only; its presence does not imply execution.

Three selected unit ZIPs have nine unique members. Each member's CRC, byte count
and SHA256 match retained extracted copies; no extraction or archive modification
occurred. The three compressed originals total 328,183 bytes. The independent
reader made **12 member reads, including three repeat reads**, with 2,099,067
expanded bytes including repeats. The collector's separate historical counter
of nine reads and zero repeats remains unchanged.

All 410 unique unit source-map entries match C's Git blobs. Six before/after maps
yielded 2,460 tuple comparisons. The exact runtime inventory is 65 Python files
and one HTML file, totaling 1,470,877 bytes. Three runtime files differ from base
`ef7508bebd35cac71d9db8fdda896806ce4ade64`; the other 63 are unchanged. C's
7,828 tracked files total 223,862,579 bytes by Git size metadata.

Retained provider metadata identifies merge commit
`c20b5aaaa64f72aa432d58d8c0fbc58d28fd72f5`, with parents base and C, and tree
`0714e6a0c3cfe6a0cfc52ca31121c819e6575590`, equal to C's tree. That merge
commit object is unavailable in the retained local Git object database; provider
metadata and local object availability are separate observations. No fetch was
performed. Source identity alone does not qualify any installed binary.

## Actual CI observations

Both first runs are completed failures. Across eight jobs there are 200 steps:
64 success, eight failure and 128 skipped. Every failed step is `Run unit tests`.
Each of the eight retained job texts contains one validation summary reporting
2,193 tests, three failures, one error, zero skips and worker exit 1. These
summaries are not eight complete method logs.

Complete logs were independently read for the fixed push Python 3.13 job, fixed
PR Python 3.13 job, and the explicitly labeled additional first-failed push
Python 3.11 job. Each contains 2,162 strict `... ok` lines. All 22 new methods
in `test_market_transition_pending` and `test_market_transition_activation_failures`
have exactly one plain `ok` line in each fixed 3.13 log: **44 fixed observations**.
The extra 3.11 observations are separate diagnostics. Neither denominator is
the reported total of 2,193. The custom component five-pure/seventeen-SQL receipt
capture remains NOT_RUN; ordinary unit lines do not establish that custom scope.

The four outcomes occur in all three full logs:

| Outcome | Exact source location | Bounded observation |
| --- | --- | --- |
| ERROR | `tests/test_process_readiness.py:338` → `uta/sharding.py:446` | The fixture supplies an invalid `halted` value through `_write_state`; strict marker validation raises `ServiceError: market transition marker is invalid`. |
| FAIL | `tests/test_native_sh_capture_protocol_pure.py:122` → `tests/native_sh_capture_fixture.py:98` | The fixture source pin is rejected with `CaptureFixtureError: fixture source belongs to another runtime`. |
| FAIL | `tests/test_durable_faults.py:1632` → `wait:1286` | The old oracle waits for `REJECTED` during partial publication; the selected source defines pending publication behavior. This static mismatch does not manufacture a successful replacement test. |
| FAIL | `tests/test_durable_faults.py:1411` | `no bound native router SH descriptor within capture horizon`. An earlier child bootstrap traceback separately reports the fixture runtime mismatch. The horizon failure's exclusive cause remains **UNDETERMINED**. |

The quoted bounded literals and frame locations were checked against C's public
source. Raw failure bodies, actual runtime identities, control data and private
paths remain private. No earlier SH cause, later fix, or repaired run is used to
explain away these first failures.

## Package, release and administration limits

Each terminal artifact inventory contains four unit archives and no package or
release artifact. The fixed push 3.13 package report is NOT_AVAILABLE; wheel,
sdist, RECORD, installed source and installed functionality are NOT_VERIFIED.
No alternate job was substituted. The prepared release archive audit draft was
NOT_EXECUTED and contributes no evidence; nested release read counters are zero.
Release qualification remains `null`.

Collector administrative history is preserved: a BOM-prefixed job text was
initially treated as REST JSON, a local merge object was unavailable, a guessed
package path was absent, and a JavaScript `TextEncoder` preparation failed before
result writing. Corrections used retained data without provider refetch or
target retry.

This independent review also records its own errors. Initial list/dictionary
schema assumptions were corrected read-only. A first reader writer had a quoting
SyntaxError before creating a reader or reading ZIPs. The first archive reader
verified the PR ZIP's three members before a wrong SAFE list-position association
assertion; event-based binding corrected the association, and all three repeated
member reads are counted above. The artifact endpoint used direct structured
artifacts rather than the other endpoints' wrapped JSON; cached CRC results were
reused after correcting that retained-data schema, with no further ZIP reads.
These are administrative reader failures, not target or CI retries.

## Delivery and rollback

The machine-readable companion is
`evidence/reviews/pr62-first-ci-independent-raw/review.json`. Only these two
review files are new. The collector's thirteen files and all sealed originals
remain unchanged. Rollback is removal/revert of this documentation-only review
commit; it performs no data migration or runtime rollback. No financial,
reconciliation, 10,000/s, HA, production, installed-package or real-funds gate
closes through this review.
