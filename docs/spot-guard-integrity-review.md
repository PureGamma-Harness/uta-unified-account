# Independent spot reconciliation and guard review

Reviewed candidate: `3729b562f0935509322e8cffd684520069145420`, independently
checked out in `/workspace/uta-migration-reverse-verified`. Production remains
unapproved. This commit adds tests, this report and raw evidence only; no runtime
or frozen release source is changed.

## Reverse reconciliation verification passed

The original four migration evidence tests and seven confirmation-integrity
tests passed independently in **2.285 seconds**, on Python 3.12.14 / SQLite 3.53.1,
with the process restricted to one available CPU. The original red test file is
byte-identical to `08ce047`: SHA-256
`7fffdaf066e36e4f6cc13d838aeb891df9fc08bc333ab9250021ec7d9068cd81`.
No original assertion was edited, skipped or marked expected-failure.

The implementation indexes confirmation events by kind/trade ID and checks
receipt/event ID sets in both directions. Each match requires one global event
with a NULL account, and two private events belonging to exactly its distinct
customer sides. Complete canonical JSON comparisons retain JSON type distinctions
such as boolean versus integer and include the recorded market/catalog versions.
Fills are indexed once by trade and order; unknown trade/order references are
rejected instead of being silently ignored. This removes the previous repeated
audit-list and order-fill scans from this verifier. Full ledger/history
materialization and the no-spot event-presence scan remain separate cost limits.

The original lifecycle control remains green: admission and cancellation of a
never-filled order may emit `SPOT_ORDER_ACCEPTED` / `SPOT_ORDER_CANCELLED` without
a trade, paired fills or a settlement journal. This review does not claim that
all possible malformed JSON cases have been independently validated.

Raw result: [independent 11-case run](../evidence/runs/spot-guard-integrity/reverse-green-py312.txt).

## Next-gate blocker: names alone do not validate receipt protection

`SpotExchange._verify()` still checks only that these four names exist in
`sqlite_master`:

- `uta_spot_matches_no_update`
- `uta_spot_matches_no_delete`
- `uta_spot_fills_no_update`
- `uta_spot_fills_no_delete`

Each can retain its original name, table, action, BEFORE timing and RAISE body,
but acquire a `WHEN 0` condition. Such a trigger never enforces its intended
immutable-history restriction. Current verification accepts all four weakened
definitions, and takeover seals each source with `initialized=1` while retaining
the corrupt SQL unchanged.

The independent tests use real settled synthetic spot history, then deliberately
damage one guard definition at a time. This is offline corruption, outside the
ordinary routed/customer writer protocol. Every case first confirms that the
original trigger blocks the protected operation. It then proves that the
weakened definition actually permits that same operation. UPDATE probes use
`price=price`; DELETE probes run inside a savepoint and are rolled back. The
match DELETE probe temporarily defers foreign keys only within its test
transaction so the exact receipt guard can be tested without deleting its fills.
Foreign-key checks are empty after rollback.

All orders, matches, fills, balances, debt and original financial/audit events
remain byte-value identical. No missing-data repair, cancellation, release of
assets, invented receipt or changed financial input explains acceptance. The
only retained defect is the weakened trigger SQL.

| Weakened guard | Original behavior | Faulted behavior | Actual verification / takeover |
| --- | --- | --- | --- |
| Match UPDATE | Rejects | Allows UPDATE | Accepts / `initialized=1` |
| Match DELETE | Rejects | Allows DELETE before rollback | Accepts / `initialized=1` |
| Fill UPDATE | Rejects | Allows UPDATE | Accepts / `initialized=1` |
| Fill DELETE | Rejects | Allows DELETE before rollback | Accepts / `initialized=1` |

The four ordinary rejection tests all fail at the reviewed candidate, with no
errors or skips, in **1.324 seconds** on the same single-CPU interpreter. Required
behavior is `503 spot_corrupt` from read-only verification and pre-seal migration,
with the corrupt SQL/evidence retained and no managed manifest, queue or fence
created. The tests preserve that requirement; they do not repair the schema.

Production writer-fence SQL verifies its own `writer_fence_data_*` guard inventory.
That is a different contract from the spot-specific immutable receipt/fill
guards; installing fencing does not establish the missing spot guard semantics.
This remains a blocker for the next migration gate, rather than approval to
weaken or bypass existing writer fencing.

Raw result: [four actual rejection failures](../evidence/runs/spot-guard-integrity/guard-red-py312.txt).
The [manifest](../evidence/runs/spot-guard-integrity/manifest.json) records source
and raw-result hashes.

## Reproduction

Run the two groups separately on the reviewed candidate plus this test commit:

```sh
python3.12 -m unittest tests.test_migration_reverse_evidence \
  tests.test_spot_confirmation_integrity -v
python3.12 -m unittest tests.test_spot_guard_integrity_review -v
```

The recorded runs used `os.sched_setaffinity` before exec to restrict the runner
and its descendants to one CPU. All test processes finished before the later
performance silence window. No new load, worker spawn or long run was started
during that window. Runtime repair and rerunning the same four guard rejection
assertions are pending with the integration owner.

The integration correction uses one official guard-definition builder for both
installation and inspection. Verification requires the exact trigger name,
object type, table and stored SQL; it does not derive the expected definition
from the inspected database. Existing official installation strings remain the
same after adding `IF NOT EXISTS`. Read-only verification installs nothing, and
the normal constructor does not replace an existing weak same-name trigger.
The corrupt definition is preserved when inspection rejects it. Static review
by the independent author found no new blocker; the same four runtime assertions,
old-definition compatibility and broader regression still need actual recheck
after the coordinated performance window. No source recovery or financial
compensation is performed by this correction.
