# Independent owned startup and spot integration review

Exact subject: `21aa6510bafcce8383fc24ac2c35e671074b9baf`, in a separate
detached worktree. This review changes tests, documentation and bounded evidence
only. It does not modify financial/runtime code, the root/integration checkout,
the frozen `720` release or any old soak authority. No large-history or
250,000-event test was run. Production remains **NO-GO**.

## Code result

No new integration blocker was identified. `_run_worker` retains the complete
spot compatibility helper inside the genuine `_OwnedStartup` context, after
the real ledger/credit/worker setup and before `finish()`:

1. Open a guarded read transaction on the initialization's bound database.
2. Assert the actual writer token at read entry and invoke the original complete
   `_verify_managed_spot_source` helper.
3. Close that read snapshot, then call `initialization.check()`.
4. Finish through keeper shutdown, fresh renewal and the final guarded writer
   COMMIT/schema check, then send the actual worker READY while actor exclusion
   is still active.

There is no post-verification expiry check against the long read's old lease
row, and no long spot scan after keeper shutdown/final binding. Spot history is
verified rather than skipped, schema/financial rows are not repaired or released,
and the final writer checks current ownership instead of the stale snapshot.

## Bounded actual verification

The existing **15 migration scope** and **13 owned-reference** tests passed on
Python 3.13.5: **28 tests, 10.524 seconds**. These retain live/partial/residual-lock
rejection, terminal history verification, mixed liabilities, schema guards,
keeper unknown COMMIT, real expiry and final writer/registry boundaries.

One additional importable test starts a **real spawned worker PID** and executes
the actual `_run_worker` entry point. It creates genuine synthetic routed funds
and debt plus terminal standalone spot history under the already disclosed
source-extension boundary. The standalone source is not represented as an
ordinary routed spot endpoint.

Only the process-control compatibility helper is wrapped, in that child. Its
unbound constructor call executes normally. Its token-bound owned call holds the
real RO snapshot for 0.9 seconds with the original 0.6-second TTL, then always
executes the original helper. No ledger, risk, credit or audit-engine function is
replaced. The original worker sends READY on its own pipe; observations use a
separate witness pipe and never synthesize a readiness or financial receipt.

The test requires:

- Exactly one pre-acquire helper call and one owned helper call.
- RO work continuing past the read's original persisted expiry.
- Actual committed renewals under the same generation and PID, with no
  replacement acquire needed to reach READY.
- An actual READY message from the original worker and a fresh active lease
  still owned by that child's PID/generation.
- No DDL in the helper's real SQL trace and identical complete sqlite_master
  type/name/table/SQL inventory after READY.
- Exact preservation of the settled financial and spot rows.

The gate remains globally halted in this fixture. Ownership READY is not a
claim of account risk acceptance or an active trading barrier. This case tests
the actual worker handshake, not an entire supervised coordinator restart.

Recorded result: **1 test passed in 1.633 seconds**. The actual worker PID was
`59763`, generation `2`; its owned read took `0.904935979` seconds with the
configured `0.6`-second TTL. Seven real renewal events committed without another
acquire, and the original helper completed before the actual READY message.
The raw observation and source/test digest manifest are retained in
`evidence/runs/owned-spot-startup-integration/`.

```sh
/usr/bin/python3.13 -m unittest tests.test_managed_migration_scope tests.test_owned_startup_reference -v
/usr/bin/python3.13 -m unittest tests.test_owned_spot_startup_integration -v
```

## Budget boundary

The child still constructs `DurableProcessRouter` before acquiring a token.
Its constructor performs the existing complete spot precheck with an unbound
reader. That work is repeated and is **outside** the owned initialization's
60-second deadline. The implementation does not establish a whole end-to-end
60-second startup bound.

Even inside ownership, the deadline is checked by the keeper and at lifecycle
boundaries; it is not a wall-time interrupt for an already running SQLite/Python
verification scan. Failure stops renewal and prevents READY, but this review
does not establish large-history latency, a universal RTO, cancellation timing,
capacity, HA or production qualification. The integrated candidate still needs
its required complete validation and separately authorized workload evidence.
