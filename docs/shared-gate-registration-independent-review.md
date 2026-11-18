# SPAWNED registration timeout: independent static review

Reviewed source: `748990b`, against runtime base
`6010e920a168b35fccfc9ef9ee34e030b28b11d9`.
The reviewed `uta/durable_process.py` Git blob has SHA256
`f2093101f7b7cf5eaa5604639a3892bcb0fd37f7421e171e242f6157416019ca`.
Only Git and source text were read. No Python, AST execution, test, SQL,
worker, signal, original private data, or native recovery was exercised.

**No additional code blocker found in this small change.** The runtime diff is
the copy import and one local database selection in `_record_process`: only
SPAWNED uses a shallow copy with `timeout=min(original.timeout, .1)`. The
registry INSERT, authority derivation, nonce, event identity, transaction role,
and all other runtime methods remain unchanged. Other registry event kinds use
the original Database object. A smaller original timeout is not increased.

`Database` currently stores path, timeout, writer token, lease clock and boot ID.
Its existing `for_writer()` already uses shallow copy to preserve the subclass
and its identity hooks. The proposed copy retains these fields and hooks,
private-file validation, connection initialization, role selection, startup
write gate, transaction guard, COMMIT/rollback, and connection-close behavior.
Changing the copy's timeout does not change the shared control Database or any
financial Database object.

Registration remains one attempt. A possible committed append with a lost reply
stays UNKNOWN, never authorizes that gated child, and never retries that INSERT
or nonce. Existing cleanup retains pending handles until exit and close are
proved. Unknown cleanup or terminal errors block replacement; only recognized
transient error plus proved cleanup permits a new child after the existing
backoff. The monitor's spawn/lease-scan order and matching-owner kill predicate
are unchanged. The lower wait budget can therefore reduce time monopolized by
one synchronous SPAWNED registration under the stated busy-handler assumption.

This is a conditional progress improvement, not a bound on `_record_process`
elapsed time. SQLite's busy-handler budget is per operation; several operations
may wait. SQLITE_LOCKED and SQLITE_PROTOCOL need not follow the same busy handler,
and WAL protocol retry/backoff, filesystem operations, process start/join,
cleanup, scheduling and arbitrary shard counts remain outside that budget.
Consequently this review establishes neither a .1-second registration bound nor
five-second native recovery. The candidate plan states these limits explicitly.

The original PR35 monitor stack is consistent with this vulnerable scheduling
point but supplies no SQL return value, exact spawning shard, or duration for
that call. This change and any finite fake-clock result cannot establish the
original failure's unique cause, actual old-owner exit/SH release, a new active
higher generation, READY, market receipts, or financial reconciliation. Those
remain separate native evidence and authorization requirements. Original CI
failure and production/capacity approval remain open.
