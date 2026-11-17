# Independent owned-startup review

Reviewed runtime: `d9afd4636a044d52bb1786eac3fd06550957ed76`, including the
owned-RO implementation from `3362fa4`, inode binding `462874a`, strict internal
context type `b6a62af`, registry-through-READY `04c418f`, complete schema freeze
`94ef45b`, and prepared-worker reuse `d9afd46`. The intermediate `e12da42`
subset-only schema comparison is superseded; its acceptance of new objects is
not the final implementation's behavior.

This independent worktree changes tests/documentation only. It does not modify
the implementation worktree's uncommitted tests/docs, the integration/root
checkout, the frozen release or an old soak authority. No large history or
250,000-event workload was run. Production remains **NO-GO**.

## Result

No concrete code blocker was identified in the final reviewed range. The bounded
component tests use actual `_OwnedStartup` instances, actual acquired tokens and
the real service constructors. Paused ledger/credit wrappers always invoke the
original complete verifier on its guarded read connection. No private verified
flag, substitute context or cached success receipt is fabricated.

| Boundary | Independent actual observation |
| --- | --- |
| Complete ledger and credit replay | Each original verifier runs once on `query_only=1`; ledger returns its true event count and credit returns its actual gross-debt count |
| Replay longer than initial lease | The ledger read snapshot remains open until at least five real `renewed` fence events commit; actual `CLOCK_BOOTTIME` has crossed the original token's expiry before full replay returns |
| Same-PID current-token writer | Another real thread's guarded financial transaction returns `initialization_in_progress`; financial projections/events remain unchanged |
| Already-open same-PID writer | A real token-bound transaction opened before scope registration commits before the entry writer barrier drains; the subsequent full read sees its actual journal event |
| New schema after replay | A real additional table causes `startup_schema_changed`; it is retained for investigation rather than dropped to pass |
| Existing module protection | A missing matching guard and a same-name weakened credit guard both cause `startup_module_corrupt`, without repair |
| Keeper COMMIT outcome unknown | A genuine renewal commits, then loses its reply; the attempt remains poisoned and does not finish despite the real successful lease update |
| Final writer COMMIT outcome unknown | The final barrier genuinely commits, then raises a synthetic lost-reply error; the scope does not mark itself finished |
| Actual lease expiry | A paused keeper attempts real renewal after its 0.6-second token expires; renewal returns `lease_expired`, the attempt is poisoned and the authority stays inactive |
| Stop during complete verification | The actual verifier runs, then stop is signalled; startup rejects before completion |
| Inode replacement | A SQLite backup is atomically substituted after real verification; identity/keeper checks reject while financial rows remain preserved |
| Entirely absent fixed modules | Original preparation creates credit/matching/scheduler metadata, never calls background `start`/`run_once`, and leaves settled cash, ledger and account events unchanged |
| Worker handoff after freeze | `take_worker` returns the same prepared worker with the requested bounded batch values; SQL trace observes no CREATE/ALTER/DROP/REINDEX after full ledger replay |

The inode test uses SQLite's backup API and does not raw-open/close the published
source inode. The in-flight case covers the same process and generation before
registration. Previous-generation/process exclusion also follows the unchanged
fence acquire/COMMIT rules; this review does not rebrand that component case as
an independent new multi-process takeover experiment.

## Source checks and limits

The public default constructors retain the original full verification path.
The managed path runs the same ledger and credit algorithms with supplied RO
snapshots, after fixed schema preparation. Required module objects are checked
against their shared compiled type/table/SQL definitions before preparation, so
IF-NOT-EXISTS cannot repair an existing partial/weak module before inspection.
Final schema validation compares the complete tuple inventory and SQL exactly.

The persistent writer fence still checks PID, generation, nonce, boot and expiry.
The process-local registry adds path/inode/thread/token exclusion, and its entry
writer barrier drains actors registered earlier. The keeper only calls the
existing lease-control renewal path. Unknown keeper outcomes latch failure;
expired generations are not revived. Final binding stops/joins the keeper,
renews the still-live token and completes a fresh guarded writer transaction.
The registry remains active through the real worker's READY-send statement.

The tests are small component interleavings, not a new end-to-end coordinator
IPC/long-history qualification. They observe actual failure/completion from the
scope; the implication that a failed scope cannot reach READY follows the
reviewed `_run_worker` control flow. Large-history memory/latency, startup work
budgets, scheduler responsiveness, disk failure, HA and financial launch remain
separate gates. The final integrated tree must preserve the other migration/spot
compatibility checks and rerun its required complete validation; this isolated
review does not attest an unreviewed merge result or the separate ledger-guard
definition correction being handled by the root group.

```sh
/usr/bin/python3.13 -m unittest tests.test_owned_startup_reference -v
```

The fixture uses only a few synthetic rows, a 0.6-second real lease, and bounded
pauses. Final result on Python 3.13.5: **13 tests passed in 3.067 seconds**.
`git diff --check` also passed. It makes no measured capacity, universal RTO, or
production claim.
