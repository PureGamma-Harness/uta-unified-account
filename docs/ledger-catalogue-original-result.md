# Original ledger catalogue gap reproduced

**REPRODUCED, not fixed.** One separately authorized observation ran on CPU4 /
Python3.12 from exact `3eaee6cc5ff764e497b5641a85ce0b1404389683`, whose52 UTA
files equal original `4ad58b2169b02f8982a1cbef8722b79d705d60c8` byte for byte.
The driver hash is `0f8d9fdb851920b5348ba38528e4480739883a1639c5da5bdba10f1c0674822f`.
Actual outer start/end were2026-11-17T15:04:25.188745Z through15:04:25.606112Z,
0.417366633 seconds including the child process; child observation was0.365630s.
No timeout, forced cleanup, second case or retry occurred. CPU4 was released
immediately. The original unmanaged synthetic database remains private; no
database binary is committed.

Public constructors and two public posts produced exactly the separately
calculated two journal events, four postings and balances a=-1250/b=950/c=300
USD minor units. The original verifier returned2 before catalogue mutation.
The original event and asset foreign keys were both present.

Offline reconstruction removed only the event foreign-key declaration from
`ledger_postings`; the asset foreign key, column/PK shape and all original rows
and seven protection trigger definitions remained. One orphan posting with
sequence99 was then inserted. Its asset USD still exists. The resulting SQLite
integrity check was `ok`, and `foreign_key_check` returned no violations: that
pragma checks only constraints that are currently declared.

The **original unmodified reopened `DurableLedger` constructor accepted this
catalogue, and its original default `verify()` still returned2** despite five
postings. The complete logical catalogue and every row stayed identical across
that constructor and verification. Source hashes also stayed unchanged. These
observations are explicit original results, not an expected-value-only test or
a monkeypatched verifier.

The gap concerns persisted-catalogue integrity detection after an invalid
offline restore/reconstruction. The service OS user is already trusted; this
does not establish a new customer permission bypass or assign a vulnerability
severity. The full managed-authority catalogue checks are a separate boundary
and were not bypassed or tested here. It does show why original classic ledger
verification alone cannot certify this malformed restore. Original data must
be rejected rather than silently declared reconciled.

The [original result](../evidence/runs/ledger-catalogue-gap/original-once/observation/result.json)
contains both complete synthetic catalogue/row snapshots and the literal
reference; [manifest](../evidence/runs/ledger-catalogue-gap/original-once/manifest.json)
binds all six raw files and the retained private database. No financial state,
product mode, API, deployment or production approval follows. Root must review
the proposed next policy before implementation or another actual SQL run.
