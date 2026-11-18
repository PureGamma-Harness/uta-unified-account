# Worker registration recovery candidate

The first PR22 Python3.11 run retained an uncaught SQLite registration error in
the supervisor thread beside a stopped-owner publication timeout. The candidate
keeps the supervisor alive when a retryable registration fails, first closes
the newly owned gated child and its resources, then retries with a new identity.
An uncertain registry COMMIT is never deleted or repeated. Unknown cleanup and
terminal errors block restart. A dead supervisor cannot report financial ready.
This is a concrete exception-path repair, not proof of the original timeout's
unique cause.

The runtime is identical to `ff814d4bcaee079b0e0503ea8072c24e3563c443`;
the component/QA source is `6b7d473c0fbf92b17c146140c88eb2c25d38dce1`.
Delivery additionally includes independently reviewed QA tools and evidence.
The running local matrix tests source6b7; it does not silently change its source
to the delivery merge. Delivery CI must separately test the integrated tree.

Nine source-pinned model cases and four first native component cases passed.
The latter combine real SQLite transactions with injected registration errors,
after-COMMIT-return reply loss and a pidfd-bound stopped process with a real kernel shared lock. Native
tracing is diagnostic instrumentation. Worker READY is not financial readiness;
the publication case ended halted and did not sample final Gateway readiness.
The detached diagnostic wrapper became a PID1 zombie; only its actual subjects
were reaped. These limits and the first model/import errors remain retained.

The first full-suite attempt lacked public reference inputs outside the six
standard folders. Its Python3.10 result is1804 tests, zero FAIL and16 missing-file
ERRORs; an import failure replaced ten real methods with one loader error,
reducing the total by nine. The
matrix stopped before Python3.12/3.13. The original failed run and supervisor
exit1 remain immutable. A separate setup materialized all6162 existing tracked
files, independently bound the full input map and preserved the351-file standard
map. The new setup's first Python3.10 result is1813 tests with zero failures,
errors or skips; Python3.12 is running and Python3.13 has not started as of this
delivery note. The three-version matrix remains in progress.
Only actual original outcomes can close those gates.

## Deployment and rollback

There is no schema migration or financial-policy change. Keep the existing
synthetic single-host restrictions and product gates. After integrated CI and
the remaining acceptance checks pass, a staged experiment must stop new intake,
resolve original command IDs, drain owned workers and verify the original
supervisor/leases before switching code. Never release an unknown registration
gate or start a second writer to bypass a recovery block.

Rollback uses the same halt, drain and exact-owner checks. Preserve registry
rows, queue receipts, ledger state and audit history. If child exit or cleanup is
unknown, retain the block and investigate; code rollback alone does not resolve
an uncertain process or transaction. No financial compensation is synthesized.

This Draft does not enable a product or real funds. Full input-bound QA,
integrated CI/package evidence, capacity, replication, disaster recovery and
independent release approval remain separate gates. Original PR22 failure is
retained and is not rerun or relabelled by this candidate.
