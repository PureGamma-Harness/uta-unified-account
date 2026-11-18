# Matching component profile: independent initial CODE review

Control H: `53739d1efdb6a1df3e33d9493eb2b1db50aee92d`; proposal OWN: `3b28fa19d2b8436926c4bc52d9d96fccade0ff47`. No target was compiled/imported, profiled or run by this review. No SQLite connection, PID inspection, signal, capability probe or network action occurred.

Status is **CODE_NOT_CLOSED / NOT_RUN** for this frozen proposal. Two deterministic preparation problems require a new source:

1. matching_profile_case.py355 compares the complete risk dictionaries from independent fresh authorities. Native service._risk includes observed_at from each referenced quote. Real UTC quote timestamps differ, so full-dictionary equality rejects otherwise equivalent samples. The same issue appears in aggregate.py241. Raw risks must remain unchanged; any finite comparable-risk/provenance separation requires an explicit contract, unknown-field rejection and independent quote/history/reference/freshness binding. It may not remove financial fields to pass.
2. matching_profile_once.py423 emits LOCAL_MATCHING_PROFILE_FUNCTIONAL_PASS_PENDING_INDEPENDENT_REVIEW, but aggregate.py144 requires LOCAL_MATCHING_COMPONENT_PROFILE_PASS_PENDING_INDEPENDENT_REVIEW. These literals disagree, so the aggregate rejects even completed targets.

The legacy risk schema has exactly ten fields: account_version, equity, initial_margin, maintenance_margin, open_order_margin, available_margin, margin_ratio, market_version, observed_at, risk_mode. Nine are non-time comparison fields; observed_at is quote provenance, not computation time. MarketSnapshot.validate defaults are max_age5s and max_future_skew1s; the original inequalities reject age>5s and age<-1s, allowing equality. A metadata correction must preserve those directions, raw timestamps and no-retry behavior.

## Other static conclusions

Current runtime UTA tree05075e8b51c8b365e46a7f5f520a625a791fd6ad equals exact C a2434bd. The original matching capsule blob e53eddde90398b59d20df2fecf019287b6f2d94e exactly equals PR35 matching.py; the other60 runtime files are shared. Current and original targets copy their intended files to separate mini-sources and require separate interpreters. No imported UTA module is swapped in-process. The original-scan constructor omits the new book_selection parameter, retaining the original API.

The independent expected matcher re-sorts price/time priority and does not call production priority/identity/fee helpers. The hand values are consistent: for32 orders, the first five selected pairs are quantity5 at102 and the next three are quantity2 at101, totaling31 units/3156 notional/1.2624 fee per account. For128 orders the first eight are quantity5 at102, totaling40/4080/1.632. USD8 makes these exact fees, not a partial-fill rounding test.

The matching call returns after its native transaction COMMIT. A symmetric cProfile and category-only SQLite trace callback observe both modes; callback failures latch. Python line-budget tracing is disabled within the finite profiled call and restored in finally with a boundary check. No hard interruption of blocked C/I/O is established. cProfile groups use exclusive self-time; cumulative times overlap. SQL and commit C time are combined, while separate COMMIT/fsync duration is null. A batch average cannot become per-fill percentiles or open-loop capacity.

Raw phase caps, logical-data allocations, strict counts/reopen/reconciliation/sample replay and builtin SQLite descriptor are finite. The JSON aggregator requires external root exit/completion and exact argv/raw/result bindings; an internal PASS alone is insufficient. The current host-receipt shape does not independently measure whole elapsed time. Root's external orchestration must retain and enforce actual phase/whole-lifecycle timing rather than adding target internal durations. These are trusted orchestration records, not remote attestation.

No further deterministic blocker was identified during this initial finite reading, but this is not a signature for the repaired source. Full physical/Git binding must match the new freeze before CODE closure. The two old preparation proposals remain NOT_RUN/zero attempts. No performance, default-scan regression, sustained10k/s, financial activation or production acceptance is granted.
