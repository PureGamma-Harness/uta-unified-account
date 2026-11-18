# Matching selector first pure run: independent raw review

**PURE_COMPONENT_RAW_PASS. No discrepancy found within the declared scope.**
Reviewed immutable first seal `037c7da6befdc17d2f45ad76bf7cf82c5a06b5ce`,
target `26fa6285afde7d38e8e811f54ac16e5816fdd79d`, and prior CODE closure
`5d65310df6ce19fc49ecb9c93af5db5dd0189eb7`. This review only read existing
Git objects, source text, hashes, byte counts and file metadata. It reran no
method and imported/executed no target, Python fixture, SQL, child, PID or network
operation. The owner's separate actual-SQL plan is outside this review.

The six original first artifacts are retained under
`evidence/reviews/matching-selection-snapshot/first-pure-26fa628-once01/`.
All five files listed by its manifest have matching independently recomputed
Git byte lengths and SHA256; the manifest correctly excludes itself. Their
listed total is8948 bytes. Materialized stdout/stderr and the four source files
also match the sealed bytes. The original scope directory is0700/files0600;
the immutable Git seal anchors the reviewed contents.

- stdout:3954 bytes, SHA256 `d51f6e7ac311ea8b23d422fec51d667e24164a44c77d6dadcbc1bcb785bbbffd`.
- stderr:0 bytes, SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- The twelve distinct declared methods each report `ok`; summary reports12
  tests,0 failures/errors/skips and actual exit0. BEGIN/END bind attempt1,
  Python3.12.14, actual affinity `[0]`, no forbidden runtime imports and equal
  four-source before/after hashes. CPU0 is the observed ID, not an inferred ID1.
- The plan SHA256 in BEGIN/intent is
  `6145486b0cadf8fcdb53fd85252cc2078f3830a0aec8b5c87b79bd2a51904615`,
  matching the sealed plan. Its four lengths/hashes match source26fa, the current
  plan and unchanged materialization-v4. That materialization records regular
  nonsymlink100644 files and exact Git blob/byte equality before execution.

The raw stream has complete BEGIN, twelve method outcomes, unittest summary and
END records. Its3954 combined bytes are below both261632 normal capacity and the
256KiB total cap. There is no cap-abort/trailer or budget-exhaustion record. The
previous CODE review checked reserve-before-write accounting, partial/error
latching, one512-byte emergency reserve and both bounded fallback streams. This
review does not claim fsync from that stream adapter.

The operation-count method passed the frozen memory assertions: one full read,
128 rows scanned and78 point reads across20 iterations. These are source-bound
assertions, not an exported per-operation trace, actual SQLite operation count,
query plan, TPS, financial settlement or module-import evidence. Likewise the
<=384-scenario/256-seed twelve-step scope is source-conditioned; per-scenario
counters were not exported in raw.

The driver's2.191063063990441 seconds and unittest's2.093 seconds are their own
reported internal intervals. `outer_monotonic_lifecycle_elapsed_ns` is null.
The recorded tool waits1.000751003 and0.000016233 seconds plus second-resolution
UTC observations do not cover the full launcher lifecycle and must not be
summed or relabeled as end-to-end latency or a benchmark.

The archived04c,88b and7a source plans are byte-identical Git blobs to their
original versions (respectively59d88881,6f89d03e,82ed7836). Their recorded
NOT_RUN/zero-attempt history is preserved. The reviewed evidence consistently
records one26fa fixture invocation, attempt1 and no automatic retry; it does
not replace an earlier result. No old suite or fixture was rerun by this review.

This result supports only the declared selected-AST/memory selector and guard
properties. Default scan remains unchanged and snapshot remains opt-in/default
OFF. Real UTA module import, SQLite, two-leg settlement/fees/risk, concurrency,
reopen reconciliation, throughput and production/financial activation remain
NOT_RUN/NO_GO. A later actual-SQL scope needs separate root authorization.
