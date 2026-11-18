# Independent CODE review: 538 enumeration and retained entry

**NOT CLOSED: CROSS-ENUM-ENTRY-001 blocks complete compared-output archival.**
Reviewed source `4ac29b30bfa69b2971a57d7ae2b70e287a607d72`, tree
`8be158c90ddce93b33b77cbef2c15f3759a7f94b`, parent
`7b449f30b417e043bf13a4f43540102b13c4d588`. Original536 review
`2ce623c8e6cdbe4225daca6affd1a4e0933eee44` and original preparation remain
unchanged. This review uses Git/text/stdlib AST/bytes only: no target import,
compile, test, SQL, native/process/PID probe, CI or child. The target remains
NOT_RUN_0, not an observed RED. External capture is explicitly OPEN; no GO.

## Specific blocker

`tests/test_cross_decimal_enumeration.py:133` and137 archive only keys from
`independent_values`. At lines148–150 the test additionally compares five
candidate metadata fields: rule_id, rule_version, catalog_version,
market_version and market_id. Neither their expected nor actual values are in
the active vector. The result adapter at
`tools/run_cross_enumeration_once.py:157` faithfully retains that incomplete
vector, subtest ID and error type; it cannot restore the missing compared data.

Static counterexample, not executed: let all financial fields be correct but
catalog_version be8 instead of7. Financial expected/actual in the saved vector
are equal, then the metadata tuple assertion fails. The archived vector does
not identify the incorrect actual version. A market_id-only discrepancy has
the same gap. Human traceback text is not a replacement for complete structured
compared-output evidence in the vector archive.

Minimal required fix: save a fixed five-field expected_metadata map before the
candidate call, then actual_metadata before the first assertion. Preserve native
scalar values and existing assertions, counts, oracle, rules and resource scope.
The last equal-rate method currently compares only the USD borrow quote; it need
not claim or archive unperformed metadata assertions. Root acknowledged this
finite blocker and plans a separately frozen delta. No fix or execution is
performed by this independent review.

## Reviewed delta properties

The two new hand cases are correct and independent of candidate bound algebra.
USD11, LTV1, equal loan IM/MM.1, step1: borrowing10 leaves equity1 equal to MM1,
so9 is the largest safe integer. USD11.01 permits10, while11 violates IM/LTV.
The last method checks every integer0..20 directly under the zero/equal-rate
constraints and separately asserts the pre-registered maximum9/10. The old two
zero-rate cases remain. Five selectors require512/6/8/8/4=538 completed checks,
not538 distinct states. The general oracle, exact input constructor, fixture
models and seed generator are AST-identical to7b449; no financial formula changed.

Each general check installs active_vector before model construction, saves
independent expected financial values before the candidate call, and saves actual
financial values before assertions. The equal-rate method follows the same
stage discipline. Failure during model/candidate/output extraction can retain
only the completed earlier stages; such a partial record is not successful or
complete actual-output evidence. The current metadata omission above is distinct
from a genuinely unavailable output caused by an earlier exception.

CountedResult retains successful groups and ordinary failure/error or subtest
failure active/completed vectors. It then delegates to original unittest
handling. With failfast enabled, first failure stops before later vectors can
replace the active record. Failure records have fixed test IDs, optional subtest
ID and error type; they do not mark failed vectors as completed successes.
The entry writes vectors before its outcome receipt. Loader errors, hard kill,
raw-budget exit or archive I/O failure may prevent a final archive/receipt;
the external caller must preserve them as FAIL/UNKNOWN rather than repair/retry.

The entry retains whole source modules, not selected financial function bodies.
Its seven-module order has all relative dependencies already loaded:
models→market→products→risk→scenario_margin→portfolio→cross_decimal_kernel,
plus inert uta.__init__, eight UTA modules total. The package search path is
empty, and the final exact loaded-set check disallows an unplanned UTA fallback.
The fixed fixture and five selectors are loaded without test discovery.
The guard denies listed SQLite imports, process/network/signal/proc/tracing
events and thread starts. This is trusted immutable-source enforcement for
this fixed loader, not a general OS sandbox or proof of every hostile bypass.

Source inputs are canonical regular reads with before/after device/inode/size/
mtime/ctime checks, pinned lengths/SHA256 and final byte/metadata recheck. New
private output is0700; JSON files use exclusive/no-follow0600 creation, flush
and fsync. Each is capped4MiB; control/vector reservations share8MiB minus32KiB.
These are logical encoded-byte limits, not hard disk, memory or blocked-I/O quotas.

The driver inherits stdout/stderr from the future parent. Python stream writes
share31744 bytes with512 reserved for an UNKNOWN trailer, leaving1024 of the
overall32KiB for caller observations. Short writes/overflow exit125 instead of
truncating into PASS. Direct/unmanaged descriptor writes still require the
future external all-FD capture. BEGIN/END and first.execution.json cannot prove
a later successful process exit, final fsync, wait/reap or EOF. Source-commit
argument is explicitly an invoker label; actual Git/source binding belongs to
that still-unimplemented external caller. This review does not invent or approve
its controller, actual resource confinement or terminal evidence.

## Frozen inputs and remaining gates

All67 canonical regular physical Git-matched pins total1,354,314 bytes. All62
UTA Python files equal7b449. OriginalCODE-plan.json is byte-identical to original
536 preparation. New plan SHA256 is
`7d994d5af9eda705644ac0fa81ba1b4568fd917d778224a5437c60b0fb139bb3`;
runner is12,343 bytes, SHA256
`898b1e9bfde80a7c970655cf8834324df9c781fb393ba66fde3c6226dedda77a`.
The source worktree was clean at this physical check. These are static bindings,
not executed module or runtime results. No source/plan/runner bytes were modified.

After the metadata fix, freeze new source/pins and independently review its
minimal delta. Then external capture/resource/actual-terminal protocol still
needs its own CODE review and unique execution GO, followed by first RAW review.
The prior independent-quote limitation remains: USD20 plus BTC.5@100 would
consume70>debt cap50 and is not jointly authorized. Full Cross/admission,
concurrency, matching, production, capacity, real funds, insurance and ADL remain
outside this pure slice and NO_GO. No data deployment/migration occurred.
Rollback preserves original536/538 evidence and removes test/control changes
only; parent financial runtime and default service selection remain unchanged.
No main-worktree/index operation was performed during this delta review.
