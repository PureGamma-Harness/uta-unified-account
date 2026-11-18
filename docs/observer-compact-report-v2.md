# Observer report v2: design and bounded evidence projection

Initial design source: `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`.
Status at design seal: **PROPOSED, CODE/PURE only; no native/SQL/observer run**.
The stopped original six-hour run and its private logs are immutable. No
continuation, replacement elapsed time or production qualification is implied.

## Observed growth, without reading authority storage

Only existing latest/before/after JSON structures, file sizes, and bounded
first/last timeline lines were read. The2,169,901,846B timeline was not scanned
or copied. Its first line is6,988B with8 command entries and no faults; the
last line is12,771,563B with34,856 command entries and159 fault entries.

The latest report's canonical `finance.command_inbox` is12,750,548B,
approximately99.84% of the12,771,563B file. `finance` as a whole is12,752,571B;
`planned_faults` is16,775B. The before/after control wrappers contain complete
31-field response objects, each with34,856 command entries. Their response
canonical sizes are12,771,559B and12,771,562B, and both retained
`stdout_complete` booleans are true. These facts do not justify calling those
two responses truncated merely because another collector retains4MiB stdout.
The actual outer collector's source/limit needs separate binding.

`read_financial` rebuilds every command's redacted summary on each observation.
`Observer.sample` embeds it, then `publish` writes the entire historical list
to both timeline and latest. Output per sample grows with history; cumulative
timeline bytes grow as the sum of those growing snapshots. The algorithm must
continue inspecting full history; presentation is the part to change.

## Consumers and the projection boundary

| Source909 consumer | Full detail needed | Disposition |
|---|---|---|
| `managed_observer_finance._golden` | Original SQL rows, journal/fills/decisions/commands | Unchanged; no SQL invoked by this work |
| `read_financial` | All query-only rows, exact watermark and per-command summaries | Unchanged |
| `managed_soak_observer.original_command_coverage:234` | Every account command ID | Before projection, unchanged |
| `Observer.sample:599` | Every terminal command state for alerts | Before projection, unchanged |
| `Observer.final_check` / `producer_audit` | Full golden/retry/watermark, reopen and source/contract checks | Before any export, unchanged |
| `managed_observer_coverage.fatal_financial_codes:103` and `Coverage.observe` | Every command's state/quarantine/retry flags, all fault and golden evidence | Run on full report before v2 projection |
| Existing finance/observer/coverage tests | Legacy full lists | Remain legacy, not replaced |

Existing observer CLI, `Observer.sample`, financial code and legacy publication
remain unchanged. New explicit `report_format="compact-v2"` is a post-consumer
API: it first invokes an explicit complete-consumer callback with the complete
report, then stores reconstructable dependencies and projects the result. A future
controller must integrate that API after its full observation, not compact the
old CLI stdout before coverage. Default compatibility mode is `legacy`.

V2 has its own schema marker and never calls a summary an empty command list.
Its display summary is not shaped as legacy finance proof. Updated coverage
entry points explicitly reject v2 before mutating coverage counters. An old
reader cannot earn golden credit from v2's summary: the legacy top-level
finance/logical-point proof is deliberately absent. Full restoration and the
original consumer are required for verification; hashes/counts are not funds
or readiness authority.

## Complete dependencies, not list truncation

All original report fields are retained in a private content-addressed JSON
dependency graph. The initial positional64-row chunk proposal at design
`c633f3773268aa172c64d2a1badedfe03fe48799` is superseded before any test: an
insertion in the first partition would shift the following chunk boundaries.
Arrays instead use immutable order-preserving Cartesian trees with stable
record anchors (command shard/sequence/ID, fault round/kind, balance owner/asset,
or the canonical value fallback). Hash-derived priorities depend on anchors,
not row state or positional offsets; in-order traversal preserves exact input
order. A fixed64-level height cap rejects degenerate trees. Each tree node has
one complete bounded record plus left/right count/hash dependencies. A prefix
or interior insertion and a state change retain unaffected subtrees. The compact report names one
root, full canonical byte count/hash, fixed counters, exact business watermark,
bounded errors and the original coverage observation. A query can restore the
entire original report in original array order and check its canonical digest.
Missing, mutated, oversized or incompatible dependencies fail closed.

The store must persist each node before publishing a compact reference. Private
nodes remain owned/private, content addressed and immutable. Raw original
private logs are not removed. V2 is an additional future format, not a rewrite
of the original timeline. Full legacy output remains an explicit reference.

For sample countS and fixed compact capR, transport/timeline is at mostS*R.
The detail store retains each distinct node once. With maximum tree heightH=64,
N initial records, I inserted records and U changed records, ordinary unique
anchor edits create at most O(N+(I+U)*H) record nodes; a contiguous inserted
block preserves old subtrees except its split/merge fringes. The fixed height
cap is part of this conditional bound, rather than an assumed random-tree
guarantee. Repeated/ambiguous identities or broad historical mutations are not
claimed cheap; their actual writes count against the same budget and fail
closed on exhaustion. A future preregistration must recordS, stable-anchor
assumptions, maximum record/node/report sizes, write amplification, store budget/free-space
floor and the measured actual persistent bytes. No6h saving is claimed now.
The private dependency directory must be inside observer output (for example
`observer/report-v2-nodes`), included in the existing aggregate control+observer
2GiB budget. It must not use an excluded private-clone path. Its own proposed
256MiB cap is an additional bound, never an exemption or a larger outer budget.

## Hand-checkable synthetic example before code

Three commands in sequence: A is an account SUCCEEDED command with no retry;
B is an account QUARANTINED command with attempts2 and a last error; C is a
control PENDING command with a last-error code. Totals are3 commands,
2 account/1 control, one per listed state,1 terminal failure and2 retry-flagged
commands. Legacy fatal classification yields `internal_execution_retry` and
`terminal_command_failure`; compact must retain that exact consumer result.

For a hand tree example, let B have lower priority than A and C. B is the root,
A its left child and C its right child, with subtree count3. Inserting D before
C alters the C-side fringe and ancestors, not A's content or priority; changing
B's state changes B's node hash without changing its ordering anchor. Actual
priorities are deterministic anchor hashes; this illustrative ordering is not
claimed to be their measured output. Restoration must give exactly[A,B,C],
the same complete-report canonical byte count/hash and the same original
coverage counters/verdict. Change B to a different state or corrupt/delete a
node: comparison or dependency verification must detect it. Pure fixtures must
also append/insert into the first of two partitions and mutate an old row.

The actual controller is source909 `tools/run_managed_long.py`. Its watch
collector reads the observer's already-written full timeline, then invokes
`classify_safely`/Coverage and financial draining. `Pipes` has a4MiB default,
while `final_once` explicitly passes the64MiB LINE_CAP. The original complete
12.77MiB final responses are therefore consistent with that separate path.
This phase provides the post-coverage codec/writer building block only; the
watch writer/collector are **not integrated** and legacy watch would still
write its growing full timeline. This is not a deployed output-growth fix.
A later opt-in writer/collector integration must move full consumption before
v2 persistence; converting an already-written legacy timeline is insufficient.

The callback must preserve the controller's `classify_safely` rollback/error
marker behavior and complete `financial_drain_before_log` for known fatal
findings **before** dependency writes can fail. Supplying a bare classification
call in a live controller would not meet that integration contract. Pure tests
use the original `Coverage.observe` as their consumer, because they contain no
real producer or safety action. This API does not silently replace the actual
controller's classification or drain semantics.

## First component-only pure result

Code source `e497e22f4f7f48f5c0c2abd53fa8e9a9bd0893c4` passed its one
authorized CPU1/10s synthetic invocation at2026-11-18T01:21:45Z:8 methods,
0.180s unittest time, exit0. The2452B original source-pin/hash/stdout/stderr
files are retained under `evidence/observer-compact-report-v2/pure-once01`.
This is a local pure component result, not native or six-hour evidence.

| Synthetic command count | Full canonical bytes | Compact bytes |
|---:|---:|---:|
|0|666|1902|
|3|1265|1903|
|64|13577|1912|
|257|52881|1920|
|1024|209401|1929|

Two partitions with512 total records initially stored514 distinct nodes.
Appending within the first partition added14 nodes; inserting inside that
partition while changing one old state added11. Every snapshot restored
strictly equal full JSON/canonical hash and original coverage verdict/counters.
Missing dependencies, bad hashes and altered visible summaries were rejected.
The full-consumer callback ran before the first dependency write. These finite
fixtures establish neither real-volume write amplification nor a six-hour
storage budget. The actual filesystem adapter was NOT_RUN.

CAS restores the complete legacy **report**, including every command summary;
it does not manufacture underlying SQL rows from a digest. Source authority
storage, private logs, code/config versions and historical snapshot/replay
dependencies must remain available for reproducing verification beyond that
report. An unavailable historical input remains UNKNOWN. Neither a hash nor
the projection grants financial authority or retrospective evidence.

## Acceptance and rollback

The independent first type-boundary review is preserved at OWN
`2d8e77201b6274f4bcb13e4098af1c21bd638660`, safely included here without
rewriting its source or raw output. Its new independent8-method batch on
e497 was4PASS/4FAIL: Python equality accepted integer/boolean/float aliases.
Those first failures remain first failures of that source.

New code `1c7b836a51dd4387013fdbf7186491e408be9f25` compares canonical JSON
bytes for publication/summary binding and requires integer protocol/node
versions. Canonicalization/fingerprinting accept only ordinary JSON types,
string object keys and finite numbers; tuples/custom objects are outside that
domain. Node decoding rejects duplicate keys and nonfinite tokens, and the
canonical finite-domain check also precedes accepting decoded node bytes.
Arbitrary Python object graphs/deep recursion are not a supported export domain.

After pre-execution source-plan commit
`55b166dc06d6fb23ae4145af8ebdb6a5bf00de5e`, the separately authorized single
CPU1/10s focused batch ran only `test_observer_compact_typed_boundary.py`:
8/8 PASS in0.009s, exit0. It covers the four known aliases, legal typed full
round-trip, duplicate/nonfinite/unsupported JSON types, full-input export-domain
rejection and writer-quota rejection after preserving the original known-fatal
classification. The previous author8 and independent8 were **not rerun**.
The new result is narrower than the whole watch/collector integration gate.
Its original files and source plan total2535B before execution metadata.

The first verification used at most one CPU1/10s synthetic-only batch: independent
legacy coverage comparison, complete round-trip/hash traversal, append-prefix
reuse, fixed report-size bound and negative mutations/missing dependencies.
No real SQL, process, observer, encryption/decryption/key use, CI, network or
new long test is authorized. Hashes on synthetic fixtures are content checks,
not signing or financial authorization.

Rollback leaves legacy mode selected and reverts the isolated new format code.
Retain original run data and all once-only evidence. New filesystem adapter
and future controller integration require independent review and specifically
scoped tests; this design does not approve real funds or a new six-hour run.
