# Exact2dda real BUSY conformance: scoped PASS only

The one authorized component used clean exact
`2dda177fc023c023f7a7d246f03c1530e4511f9d`, helper SHA
`0768f4bc76e808dab4eb05f2844dface420de335ed146bb2c673d75db08236e1`,
and test SHA `389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6`.
Actual interpreter: `/usr/bin/python3.13`, Python3.13.5/SQLite3.46.1, CPU2.
All265 source/helper inputs remained unchanged and clean; native runtime bytes
still matched8b. The native component was not repeated.

Actual whole interval was **2026-11-17 14:28:13.434799 to 14:28:14.151294 UTC**,
0.716489 seconds. The worker portion was0.441730s. The whole-duration check is
separate: a27-second watchdog alone cannot establish total duration<=30s.

The own scratch child PID214273/birth6282014 acquired generation1 and a real
five-second token plus native router SH. A fresh parent read observed it active
before the child took its real zero-DML SQLite EXCLUSIVE transaction. After
the parent's own bound pidfd SIGSTOP, actual native status returned
**SQLITE_BUSY(5)**. The undo helper restored that exact child with SIGCONT,
performed zero native lease reads, and preserved the original exception object.

The child really rolled back/closed its transaction and released SH while
remaining alive at a final barrier. One fresh .1-second read then confirmed the
same owner/generation active, with expiry `62825414160711` unchanged. There was
no renewal, replacement token or active value fabricated from an unknown read.
Actual parent phases were fresh-before, expected-real-BUSY and once-fresh-after.
The child subsequently released its own authority and exited normally.

Full fixture financial snapshots matched. The original driver actually asserted
the integer map `customer:scratch=1000`, `system:custody=-1000`. Raw trace records
the predicate result rather than expanded balance rows. This is a bound driver
assertion and snapshot comparison, not an independent cold database replay.

All11 worker predicates are literal true. A separate derived strict AND checks
raw/source/helper hashes, actual code5, exception/zero-read/fresh-owner proof,
whole duration and cleanup; exit0 alone is insufficient. No watchdog, logger
error, cleanup error or forced cleanup occurred. The native child and session
214271 had no remaining process rows afterwards.

Six safe originals, their copy hashes and the separate derived acceptance are
under `evidence/runs/shared-gate-busy-read-8b/controlled-2dda-once/`. No complete
private SQLite/WAL directory or owner nonce is published. No old job was
queried or signalled.

This intentional EXCLUSIVE microcomponent validates the real BUSY undo helper
contract. It does not establish the historical WAL cause, manufacture native
protocol15, rerun overall publication or qualify full8b. The seven synthetic
protocol-vector definitions were not executed under this authorization. Original
local/remote8b failures and prior3af evidence remain unchanged.

`component_passed=true` is scoped to this run; `full_source_qualified=false` and
`production_approved=false`.
