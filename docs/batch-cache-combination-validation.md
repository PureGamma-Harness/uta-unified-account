# Combined durable batching and NORMAL supervision cache checks

Scope: immutable runtime `74e03a8fc7e3265cb03a3ffa0ffcaeac88fc35fd`, integrating
both independent runtime flags. This branch changes tests and evidence only.
Synthetic customers and funding are used throughout. It is not a performance,
full-suite, package, remote-CI or production qualification.

Three small tests exercise the merged contracts:

1. A real spawned owner starts a fresh `durable_batches=True` authority with
   `financial_batch_size=3` and `normal_cache_size=8`. Call-through observers
   execute the original complete ledger/credit verifiers, check their real RO
   transactions, and confirm the exact native prepared worker is transferred
   cold with capacity 8. Real background rounds warm the cache before three
   original commands enter the batch dispatcher. Every command receives its own
   committed financial receipt, reserve 10.04, unique order/event and audit
   decision reference. Retries retain the original command receipt, and the
   unchanged settled balances/journal are checked after closing the owner.
2. Another actual owner uses batch limit 8 and cache 8, warms, and stops only
   after the original `BatchStore.prepare` has committed three original members.
   SQLite inspection proves no outcome or order yet exists. The test kills that
   worker; its real replacement has a new PID/generation, performs complete RO
   startup verification and transfers a fresh cold capacity-8 native worker.
   Call-through recovery reads the actual immutable RECOVERED outcome, and the
   READY send observer reads zero unresolved manifests and that same outcome
   **before** forwarding the original READY. Recorded monotonic ordering and
   immutable PENDING member snapshots verify recovery precedes READY. The three
   original command IDs then settle once through the real admission authority.
3. CLI parsing and `_runtime` preserve both simultaneously supplied flags.
   Boolean and out-of-range programmatic arguments fail configuration validation
   before creating an authority; invalid CLI values exit 2. Both defaults remain
   zero. The test checks the exact exception type, not the broader `ServiceError`
   subclass that could merely report a later missing-layout error.

Observers never replace financial results, clocks, matching, verifiers or
receipts. Native functions run first, and observations are diagnostic JSON only.
Post-verification SQL tracing rejects any CREATE/ALTER/DROP/REINDEX statement
through actual READY. The recovery observer queries committed SQLite records.
The actual `.005` second batch soft budget is unchanged: a three-member manifest
may execute only a prefix. Tests retain actual nonempty `executed` lists of size
1..3 and require all three eventual unique financial receipts. They do not
claim three orders necessarily shared one COMMIT or infer throughput from
membership count. All orders have the same direction, so these examples produce
no matched fill and do not qualify liquidation or execution capacity.

The scheduler observation budget is eight seconds, including the existing
five-second lease of a killed owner; production TTL and business timeouts are
unchanged. The dispatch test pause is separately bounded at two seconds.

The first development run had an instrumentation failure: only initial spawn
was wrapped, so the real replacement was READY but wrote no native observation.
The corrected test retains its call-through spawn observer until router close.
That first log is preserved separately and is not a runtime-defect finding or
a qualification result; exact original instrumentation source hashes were not
retained. Final evidence must identify the committed test source and original
74e runtime hashes. `UTA_BATCH_CACHE_TEST_EVIDENCE` optionally stores actual
post-COMMIT diagnostic observations for these small tests, without copying or
moving authority databases.

Run one small suite on one CPU:

```bash
taskset -c 0 python -m unittest tests.test_batch_cache_integration -v
```

No live schema/config migration is introduced. Zero numeric flags stop new
batch grouping and NORMAL suppression; a batch-capable authority still requires
capable code to recover existing attempts before READY. This does not turn its
persistent batch capability into a legacy authority or authorize old-binary
rollback. A new
root freeze must independently run full correctness, CI and package gates. No
previous 38- or 105-test result is promoted to that scope.

Final committed tests `af6cf5c` passed three cases on each of CPython 3.10.22 /
SQLite 3.53.1 (6.775 s), CPython 3.12.14 / SQLite 3.53.1 (6.767 s), and CPython
3.13.5 / SQLite 3.46.1 (7.807 s), sequentially on CPU 0. Original logs, actual
financial/native/recovery observations, source hashes and the actual driver are
retained in [the evidence archive](../evidence/runs/batch-cache-combination/README.md).
The archive also preserves the intermediate run and initial instrumentation
failure with their narrower evidence limits. Runtime files remain byte-identical
to the fixed 74e base. No corresponding production or capacity claim is made.
