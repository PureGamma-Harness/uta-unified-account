# Ordered postings attempt 01: NO_GO, first-error regression reproduced

Exact candidate `52d2a4cc6edfe5b8f11146b6472274746135a6e3`, runtime first introduced in `56de743`, harness `0a2f4e2`. This is an author-run synthetic component, not independent acceptance. Root approved one CPU4/Python 3.12 attempt after the catalogue group released the CPU. The original runtime and all controls remain unchanged after the observation; no retry or repair run occurred.

Actual outer interval: 2026-11-17 15:05:13.979237–15:05:14.601051 UTC, **0.621792665s**, CPU4, exit 1, watchdog false. The single child PID 233118 was reaped. Runtime/test/harness SHA256 match before/after. All loaded UTA source fingerprints match before/after in the retained summary. The actual differential ran **23 test methods, 4 failed subtests, 0 errors, 0 skipped** in 0.339s. The four failures occupy two methods, so neither “19 passing methods” nor “four failing methods” describes the result correctly. The other 21 methods completed successfully.

| Declared multi-fault control | Original/default first result | Ordered stream first result |
| --- | --- | --- |
| First event chain broken; same event account contains invalid UTF-8 TEXT | `LedgerError: journal sequence or hash chain is broken` | SQLite `OperationalError` decoding `account` |
| First event chain broken; same event units contains invalid UTF-8 TEXT | Same original chain error | SQLite `OperationalError` decoding `units` |
| First event fingerprint broken; next event account contains invalid UTF-8 TEXT | `LedgerError: journal event fingerprint changed` | SQLite `OperationalError` decoding `account` |
| First event fingerprint broken; next event units contains invalid UTF-8 TEXT | Same original fingerprint error | SQLite `OperationalError` decoding `units` |

The original guards/catalogue remain in these cases. The row decoder runs during the initial/next lookahead fetch; financial canonicalization is not the only possible error point. Root's static hypothesis is now actually reproduced. These are observable diagnostics/order regressions in a disabled local experiment; no exposed service, accepted trade, lost money or production incident is demonstrated.

The original invalid-asset case still hit the foreign-key check before either path reached event replay. Other executed controls cover literal manual balances/hashes, physical insertion order, option types, original/default/new SELECT dispatch counts for the two-event fixture, missing groups, orphan inventory under the original FK, sequence/ordinal gaps, canonical order, hash chain, signed integer bounds, both cumulative overflow signs, final balances and protection/schema/scales.

The harness immediately failed its differential gate. **Profile calls = 0.** The N=512/P=1024 fixture, alternating measurement calls, physical read counters for those calls, and final N=512 default cold reopen were **NOT_RUN**. The small two-event dispatch assertion is not a measured 512-event or large-history speedup. No performance improvement, recovery RTO, throughput or production qualification follows.

## Evidence and rollback

Original external files remain at `/workspace/uta-history-perf-evidence/attempt-01` and `/tmp/uta-history-postings-52d-once`. The public [attempt directory](../evidence/runs/history-perf-rnd/attempt-01) contains byte-for-byte copies of the allowlisted launch/summary/phases/unittest/stdout/stderr and a SHA256 manifest. No database, auth, TLS or secret material is included. Test-private databases were cleaned up by their fixtures; no production authority or old job was opened.

Do not enable or integrate this opt-in candidate as accepted. Default callers continue the old path; rollback requires leaving the option false or omitting this separate R&D branch. No schema/data migration occurred. Any repair must use a new immutable candidate and a newly authorized bounded observation, preserving this original red result. Another group must independently review the proposed repair; the author cannot sign its own acceptance.
