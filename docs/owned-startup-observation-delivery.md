# Owned-startup lease observations: bounded diagnostics, Draft delivery

This delivery records lease/replay entry facts that ordinary test tracebacks
lose. It adds no read-admission repair or financial authority. The two UTA
modules and validation tool are exactly the independently reviewed6303ed4
bytes. Default execution collects optional observations: this feature is
**not default OFF** and has no new runtime enable flag. PR38's unrelated D2
companion exporter remains default OFF as inherited from17e0838.

## Assembly and unchanged decisions

The branch starts from published PR38 tip
`17e0838ff0c153f36ec53a03e4db219e5948ab33`. Its UTA and validation-tool bytes
match original9b4. Two explicit history merges preserve author tipb59106c
and independent review tipa202499; no base tree was overwritten. PR38's D2
source/config and both first failed CI records remain untouched.

The observation changes in `uta/writer_fence.py`, `uta/startup.py` and
`tools/run_validation.py` retain exact6303 bytes. A fourth executable source,
`tools/run_managed_variants.py`, adds the separately reviewed/planned strict
worker-report compatibility gate described below. Original SQL, transaction
context/COMMIT, source clocks, token identity and expiry refusal, full ledger
and credit verifiers and READY policy remain their original decisions. A
private error annotation preserves the original business exception identity,
args, code and chain; no error is converted to success. No schema or durable
financial data migration, new REST/WebSocket route, public account field or
customer error contract is introduced. All metadata remains outside admission,
check/finish/READY/retry and financial calculations.

Observation work does affect execution timing. Every read TransactionGuard,
including unmanaged/unbound reads, adds monotonic sampling and primitive-map
work; guarded writer assertions add a registry-lock lookup and optional read
observations. Receipt/annotation/collector paths add work too. Successful-path
KeyboardInterrupt/SystemExit cancellation propagates; an already propagating
business primary cannot be replaced by optional annotation failure. There is
no timing, throughput, lock-contention or memory-allocation equivalence claim.
Tight leases can be affected by overhead; no lease/keeper/deadline is extended.

## Private observation and validation-report contract

The origin-tagged `_uta_lease_observation_v1` attribute is an internal immutable
primitive snapshot, not a capability or public API. Current producers write
`version:1`. Strict native integers are bounded0..2^63−1; bools do not pass as
integers. Only fixed fields and enums are copied, inspecting at most64 entries.
No raw nonce, authority ID, boot ID, arbitrary exception dictionary, message,
repr, frame local or post-failure database read is added to the projection.
Missing metadata means unknown, never zero or a healthy state.

| Field family | Unit/domain | Meaning and boundary |
| --- | --- | --- |
| `assert_row_observed_ns`, `assert_row_expires_ns`, `assert_now_ns`; guard/renew/last-known row values | Nanoseconds, original `fence_clock_ns` | Same-domain source-row values and original assertion clock; system BOOTTIME or its explicit injected clock, not wall time |
| `*_load_started_ns`, `*_lease_fetch_started_ns`, `*_lease_fetch_finished_ns`, `*_load_finished_ns`, `guard_validation_finished_ns`; attempt/last-known start/finish | Nanoseconds, `monotonic_ns` | Existing load/fetch/validation or call-observation intervals; **not SQLite snapshot establishment time** |
| `snapshot_time_known` | Boolean, only false accepted | No snapshot creation timestamp is asserted |
| `*_generation`, `renew_attempt`, `last_known_renew_attempt` | Dimensionless integers | Diagnostic row generation/attempt sequence, no fencing token grant |
| `phase` | Fixed enum | `ledger_read_entry`, `credit_read_entry` or `renew` |
| `renew_attempt_state` | Fixed enum | `pending`, `known_commit`, `returned_unobserved`, `failed_or_unknown` |
| `renew_known_commit`, `last_known_renew_same_token`, `identity_matches` | Booleans | Facts already established at the original point; no claim of a currently live lease or verified financial snapshot |

Never subtract values across the two clock domains. Fetch intervals cannot
date the snapshot that SQLite established earlier. A last-known receipt is
copied only after the exact existing renewal call reports COMMIT success and
its private token reference matches the scope token. A COMMIT-unknown or
post-COMMIT wrapper error leaves the new attempt unknown and preserves the
separate old known receipt; neither clears keeper poison or authorizes READY.

The validation worker/summary may now contain optional v1 diagnostic fields
`lease_observations` and `lease_observations_truncated`. The current tool emits
both even when empty. Each capsule is `{test, lease}` with a bounded ASCII test
identifier, up to16 capsules and4096 compact-JSON bytes per field map; the
sum of compact capsule lengths is at most65536. These are logical collector
bounds, **not a hard cap on the whole indented worker JSON or raw traceback**.
The original unittest addError bookkeeping/traceback runs once before optional
collection. Consumers must not promote observations to qualification or
authority. Older records without these keys remain older records, not missing
financial proof. The collector filters primitive types; it does not independently
enforce the numeric version equals1 or create a new approval schema.

## Existing consumers and explicit compatibility limit

Static source inspection, without executing any consumer, found:

| Consumer | Existing behavior with added keys |
| --- | --- |
| `tools/run_validation.py` parent | Spreads worker fields into summary; existing pass/count/source checks remain |
| `tools/managed_soak_observer.py`, `tools/managed_observer_smoke.py`, `tools/run_spawn_recovery_full3.py` | Read required existing keys and compare original counts/source/exit; extra diagnostic keys are not approval input |
| `tools/run_managed_variants.py:qualification` | Accepts exact legacy7 or exact new9 worker keys. Either report's reserved diagnostic pair, when present, must be complete, a native empty list and literalFalse. Original source/count/runtime/log/CI gates remain |

The old consumer would reject every new worker record with `QA worker result
fields`. Its minimal adapter now admits exactly two complete grammars: the
original seven keys, or those keys plus both diagnostic fields. Unknown keys,
half extensions, nonempty/truncated diagnostics, collection aliases and0/None
instead ofFalse reject. A W9 worker requires both summary fields. A W7 worker
may pair with a valid S9 summary; the summary's reserved fields are independently
validated even with a W7 worker. Either summary half-pair or invalid value
rejects. Unrelated summary metadata retains its original compatibility. The
existing per-key type/value equality check is retained. No canonical projection
or rewritten worker record is needed: original9-field artifacts stay complete.
The adapter does not admit a passing capsule containing a lease failure and
does not reuse old qualification for new source. All earlier qualification
conditions, including exact-source binding, remain authoritative. Its separate
six-method/32-case pure preparation is NOT_RUN until its own review/budget.
The earlier81a1af9 preparation/plan was never executed; independent CODE review
found its missing W7/S9 summary validation. That static finding and zero-attempt
source are preserved; it is not a test RED or a runtime incident.
No old spent job, PENDING snapshot or report is rewritten.
Customer API consumers are unaffected because these fields are private test
artifacts, but a whole-CI result for this delivery is still NOT_RUN.

## Evidence and gates

| Evidence | Exact scope and result |
| --- | --- |
| Baseline5af6cb0 / sourcea95838b | Eight methods/30 model traces;27 matching and3 conditional RED; not an explanation of real CI errors |
| Source88da96f, sealed47dfa75, independent85a3d3c | Twelve methods:11OK/1FAIL/0ERROR,45 entered; fake copied-counter assertion failed;3 later m08 selectors and a later known-case assertion untested there |
| Corrected sourcebf48ae2, sealedb59106c, independenta202499 | One explicitly selected m08 method/four original selectors PASS, no retry; other11 test bodies not rerun |
| New strict consumer adapter | CODE-only preparation:6methods/32 independent examples executing the actual QA prefix with memory proofs; no execution yet; package/installed/omission gates excluded from that fixture |
| This merged delivery | Static assembly/compatibility/materialization only; no new test, SQLite, native worker, build, package or CI execution |

The three observation runtime/tool files retain their exact approved source;
the additional control-layer adapter has its own CODE/focused-test gate. Those CODE
reviews and pure/fake results do not establish SQLite/WAL snapshot timing,
keeper scheduling, contention recovery, five-second behavior, HA or capacity.
No old48/all12/full-suite green is claimed. Original PR38 push/PR whole failures
and each original error's UNDETERMINED cause remain intact.

Phase2 remains NO_GO: owner-thread financial writes are permitted, post-ledger
policy writes exist and no sufficient composite financial/schema watermark
or complete factory exclusion proof is available. A new same-token head cannot
authorize an old financial snapshot. Production, real funds, native recovery,
10k/s, HA and model/financial approval remain false.

## Synthetic deployment and rollback

1. Root reviews the final frozen commit and may publish a Draft/first CI.
   Retain first push and PR outcomes separately, including any failing jobs;
   no rerun or green implication follows from this document.
2. Build/install verification and any native synthetic check require their own
   authorization/gate. Until then, use source review only. Packaging selection
   is checked statically; no local wheel/sdist build was performed.
3. A later authorized deployment uses an independently pinned **fresh synthetic
   layout** and explicit artifact/code identity. Existing code-bound authorities
   cannot accept a binary hot swap, marker rewrite, copied database or ignored
   identity mismatch. This delivery defines no qualified live upgrade path.
4. Observe raw errors and optional diagnostics separately. Preserve missing,
   truncated and UNKNOWN evidence; no automatic replay, renewal revival,
   financial retry or cached-head admission is introduced.
5. For a code rollback, retain the new layout and every command/receipt/raw log,
   stop new traffic under the separately qualified lifecycle, and use the
   previously pinned binary with a compatible independently prepared layout.
   Do not point the old binary at a changed code-bound authority or rewrite its
   marker. No confirmed trade or financial history is deleted or reissued.

There is no schema/data rollback here because no migration is performed.
Failure to establish a safe ownership/code binding is NO_GO, not permission
to bypass the fence. Real-funds enablement still requires independent review
and explicit launch approval outside this Draft.
