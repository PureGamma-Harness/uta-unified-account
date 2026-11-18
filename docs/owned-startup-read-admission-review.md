# Owned startup: read-snapshot admission and lease progress

Current stage: phase1 observation CODE is implemented at6303ed4 and has a
separate independent CODE-only review. The12-method/48-trace closure frozen
at72dcebf has **NOT_RUN**; its independent fixture/driver review and exact root
once budget remain pending. Phase2 remains NO_GO. The baseline/source-order
assessment below and the first3RED result retain their original frozen scope.

The baseline CODE/model review is based on source
`9b4fcf5df3615c8bcddc8dc37cb35f9a24d21439`, whose entire `uta/` tree equals
base6010. That baseline delivery changed no runtime or original test. Current
phase1 changes only private observations in writer_fence/startup and the CI
collector; original tests and admission remain unchanged. No SQL, database, native
worker, thread, process, signal, network or real sleep is executed by the model.
This branch is separate from shared-gate registration and readiness-case work.

## What the two first errors establish

The collector's fixed safe projection is commit
`39b1d14a970442b9452213f8af1b73d6fee03243`,
`evidence/runs/pr38-first-ci/failure-classification.json`,10,906B/SHA256
`00c179cf9871b67d087d274ac546b432502f24b2fa9f976147315cfdc005c146`.
Its push44231349622/Python3.12/job134556896833 ran2,102 tests with zero failures,
two errors and zero skips. The original ZIP/log custody belongs to that
collector; this review reads only its safe projection and frozen source.

Both errors reach service.py:189 → startup.py:312 → writer_fence.py:533/295,
where the row visible to assert_writer has expires_ns <= the current clock.
That does not establish whether the current durable row had also expired.

| Original case | Last established phase | Not reached |
| --- | --- | --- |
| owned-startup credit projection corruption | First ExchangeService constructor, read-entry writer assertion | The full ledger verify call at313, CreditService construction, expected credit_corrupt assertion |
| unrelated authority normal financial path | The fixture's first ExchangeService constructor | Creation of other.sqlite3, its account/deposit path and final startup finish |

The case names do not prove replay already succeeded. The two cause histories
remain independent and UNDETERMINED; a shared exception does not prove a shared
cause, replay cost or scheduler delay.

## Actual source budgets and sequence

| Budget or condition | Actual value | Meaning |
| --- | ---: | --- |
| Both error fixtures' lease |0.4s /400,000,000ns | Expiry remains strict; the separate producer-contention test's5s override does not apply |
| Keeper target interval | lease/3 ≈0.133333s | Scheduled from last renewal start, not a hard OS progress guarantee |
| Keeper SQLite busy budget | min(DB timeout10s, lease/12,0.1s) ≈0.033333s | Driver wait parameter, not a bound on every SQLite/filesystem/OS action |
| Owned write-gate wait | min(startup deadline, now +lease), acquire slices ≤0.05s | Financial/control scheduling; read role does not acquire this gate |
| Whole startup deadline |60s default | Distinct from the lease; never substitutes for liveness |
| Stop-keeper join |1s | Must confirm thread stopped; no successful finish if still alive |
| Production router default lease |5s | Unchanged; not this fixture's lease or a new verified native deadline |

The source order is acquire live token → register thread-bound owned scope →
start keeper → drain prior writers in a short fenced write → construct trading,
ledger and fixed schemas → full ledger RO replay → fixed policy writes/full
credit RO verification → stop keeper → fresh same-token renewal → final fenced
no-op/schema-check COMMIT → mark finished → READY publication. Batch mode also
resolves original attempts and renews before its READY path.

Database.read_transaction executes query_only, BEGIN and TransactionGuard
creation before yielding. TransactionGuard._load makes the first read snapshot;
control-schema/data-guard validation happens in that same snapshot. Only after
it yields does verify_ledger call assert_writer. That function reloads the same
snapshot and compares its lease expiry with a newly sampled current clock.
The comment at startup.py:315 correctly avoids a stale post-replay expiry
check; it does not remove this read-entry snapshot/clock window.

```mermaid
sequenceDiagram
    participant I as Owned initializer
    participant S as RO snapshot
    participant K as Lease keeper
    participant D as Current durable lease
    I->>D: acquire same token, expiry400ms
    I->>S: first read at100ms: snapshot expiry400ms
    I->>S: validate snapshot schema/guards
    K->>D: known renewal COMMIT at300ms, expiry700ms
    I->>S: entry assert at450ms sees old expiry400ms
    S-->>I: lease_expired
    Note over I,D: Conditional source-admissible false rejection; not either CI error's proven history
```

This is a structural, hand-computable **candidate**: the current owner can be
live after a successful same-token renewal while its older RO lease row is
expired. No guarantee on schema-validation duration or scheduling is assumed.
Conversely, a genuine expiry before renewal must still refuse. The first
bounded baseline model is intended to retain that distinction, including RED
for the candidate false-rejection traces, rather than changing the old errors.

## Safety obligations for any repair

| ID | Required invariant |
| --- | --- |
| OS1 | Ordinary renewal requires the current token to be live before the update; exact expiry equality refuses; no expired revival |
| OS2 | Snapshot authority/nonce-binding/generation/PID/boot must agree with the exact live token; a new current generation cannot certify an old snapshot |
| OS3 | Unknown renewal reply, keeper failure, scope revocation, stop, parent loss or deadline prevents finish; known current row alone cannot wash uncertainty |
| OS4 | Original complete ledger/credit verification and schema checks still execute; no cached success or partial replay permission |
| OS5 | Every mutable financial projection remains at the verified snapshot watermark, or equivalent exclusive-actor reasoning is separately proved |
| OS6 | Financial DML and final COMMIT keep their current native fencing and expiry checks; RO admission never grants DML |
| OS7 | READY is based on the successful fresh final COMMIT linearization point; delivery after arbitrary OS delay is not a lease promise, and later admission still checks current authority |

OS5 is an explicit implementation obligation. The current source has no
declared single persisted watermark covering all financial projections. A
ledger MAX(sequence) alone, a refreshed cache or a snapshot-start clock is not
such a certificate. The finite model's watermark is an abstract specification,
not a field claimed to exist or a proof of actor exclusion. Owner-thread
exclusion and each permissible write between snapshots must be reviewed before
an implementation can replace this obligation.

## Missing observations and bounded first model

The original errors retain neither snapshot lease sampling time/expiry nor
current keeper renewal COMMIT/known-reply timing. They also lack the exact gate
wait/held intervals and a current-versus-snapshot binding comparison. Genuine
lease expiry, a concurrent successful renewal hidden by the snapshot, and a
keeper/response failure are distinct source-admissible histories. None is
selected as the original cause here.

Future diagnostics should record bounded phase/time fields, identity hashes,
generation and snapshot/current observed/expiry values with explicit clock
domain. Raw nonce, key, row contents or a renewed success fabricated after the
fact must not be logged. Observing a current row after failure is evidence only;
it must not automatically retry, promote READY or revive the old command.

The first model source evaluates only original pure _observed/_assert_token
AST, with fake typed row/token/clock values. Lifecycle/READY and financial
watermark policies are explicitly source-corresponding abstractions. Eight
methods plan30 small traces, including three expected baseline RED for legal
committed renewals hidden by old snapshots, genuine expiry, identity changes,
keeper uncertainty, revocation, full verification, watermark change and final
freshness. All numeric lease values stay0.4s. The model is NOT_RUN at source
freeze; it supplies no native, financial or original-cause approval.

### First baseline result retained

The separately root-authorized first execution used frozen source
`a95838bc8a3595be98aa0092eb73cd69162768a4` once: eight methods/30 small traces,
27 matching controls and three expected conditional RED, zero errors, exit1.
Unittest reported0.012s; outer elapsed76,146,311ns. All ten source pins match
before and after. CPU1 was requested through taskset; child affinity was not
independently sampled. Complete stdout391B/SHA256
`c3dcbaf5cf926db6168f706f08083649776cbd21f984940971166dc5f18fc358` and
stderr4,402B/SHA256
`76b19794a73a69af207dda7eb01226a68418ef7feb0382240b4637e6fd06fd47`,
intent and execution are preserved under baseline-first. The preparation plan's
NOT_RUN field remains the original source-freeze state, not the current result.

The three RED are conditional source-admissible witnesses, not observed native
failures or a proof of either original CI error's cause. No original test or
runtime, TTL, keeper interval, deadline or expected rejection was changed. The
first result is not rerun or converted into a successful baseline.

## Next implementation gate and rollback

After the first witness is sealed, a minimal CODE proposal may add a private
owned-RO admission primitive: exact-token known fresh control binding using the
unchanged TTL; match immutable snapshot identity; require the full financial
watermark/exclusion obligation; run original complete RO verification; then
retain the existing fresh final fenced COMMIT. It must not globally relax
WriterFence._assert_token or treat old snapshot expiry as current authority.
It must cover verify_ledger, verify_credit and review the analogous managed
spot/batch-history RO entry sites; fixing just the two observed frames is not
a general solution.

No runtime patch is authorized by this model alone. The specific primitive,
real watermark/exclusion proof and independent tests require separate review.
No lease/test/deadline increase, swallowed exception, automatic retry, stale
success cache or expired renewal is an acceptable repair. Reverting this
review removes only new docs/model/evidence; it leaves all first errors,
existing fencing, private authorities and financial history intact.
