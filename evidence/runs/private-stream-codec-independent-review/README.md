# Independent c7 mutable-header regression: blocked candidate

Runtime `c7bbd41f1e4ea48961a59921826f80c585c34e6d` is unchanged. Three independent
small pure cases exercise the **public** `WireFrame` constructor with ordinary
bytearray/memoryview headers. Default encoding factories create bytes headers,
so this is a component-constructor contract defect, not an exposed listener or
financial exploit. No socket, SQL, service or external runtime was started.

The first actual run has two failures and one error: bytearray mutation changes
queued `810178` into `8201797a78`, expands actual wire size from3 to5 while the
recorded size remains3, and releases the accounting to **-2**. A memoryview
header is accepted but public `to_bytes()` raises TypeError. Source, test hash,
original complete log and observations are retained under `original-c7`.

The next pure reference observation explicitly materializes the externally
expected header/payload bytes without calling `to_bytes()`, so it can exercise
the memoryview queue path despite that existing TypeError. That unchanged c7
runtime then produces three actual failing property tests. Both runs remain
original failures, not overwritten by later candidate results. Exact inputs,
argv, timestamps and hashes are under `original-c7-direct-queue`.

The proposed author's separate fix rejects nonexact-bytes headers before
payload inspection/copy. Its source must be independently checked and these
same test properties rerun against the new immutable candidate. No original
source or result is retroactively changed or promoted to a runtime pass.
