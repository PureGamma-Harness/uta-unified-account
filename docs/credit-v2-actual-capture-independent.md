# Actual credit capture: independent verification contract

Initial preregistration status: **PENDING_ACTUAL_CAPTURE**. The scoped actual
BORROW SQL/oracle result appended below is now PASS; broader execution gates
remain pending. This work is separate from production
valuation, transition, capture and replay code. The reference math and eight
manual vectors were committed first at `2b83a47`, extended at `205abbc95`.
This adapter starts from integration `e7b26ec` and reads only retained data.
It imports that owned integer/Fraction oracle, never any `uta` module.

The first supported export is the author's published seven-field observation:
original source, durable inbox, staged intent, declared expected-posting rows,
original credit receipt, actual journal and complete dedicated decision bundle.
The expected-posting table is checked against independently derived legs; it
never supplies expected financial effects. The original receipt must point to
the actual ordered journal, and every original CID/account/source/SID/decision/
allocation/intent identity must agree. Different fields cannot substitute for
each other merely because their content hashes are internally consistent.

The adapter maps gross positive cash, negative cash deficits, frozen balances,
separate principal and interest including their negative liability ledgers,
pool, receivables, aggregate shard exposure, live orders and linear positions.
The independent oracle determines the quote and permitted static allocation,
cash/principal/pool transition, four borrowing legs, before/after risk and
margin decomposition, conservative risk quote, version advance and receipt
amounts. Published static/risk/product/market parameters are translated to that
oracle; unsupported currencies, modes, products and fees fail closed. It does
not silently substitute defaults for observed monetary inputs or accept
unjustified asset/debt netting. The risk E/MM diagnostic ratio uses a separate
integer implementation of 34-significant-digit HALF_EVEN rounding.

The content checker also verifies canonical source/command and dedicated
decision identities, original market/policy/artifact references, all three
retained UTC checkpoints and original journal hashes. The physical COMMIT
timestamp remains null. Retained interest-cash balance is absent from this
borrow-only contract; a neutral zero is used only in the oracle state, and the
report explicitly says that balance was not observed. Repayment verification
will require separately observed interest cash and does not reuse this claim.

Passing file content is **not** proof of SQL origin, native authority, FIFO
selection, two COMMIT boundaries, durability, an actual prior journal head or
successful restart. The output always leaves that provenance pending. Actual
verification requires the real producer source+PENDING COMMIT before the
financial native operation; the latter must retain the original receipt,
four-leg journal, decision and SUCCEEDED terminal in one financial COMMIT.
Reopen/query and unknown-response checks require separate independent
execution evidence. A fabricated specimen can never authorize the system.

Planned command, only once actual author evidence is available:

```sh
python scripts/credit_v2_capture_reference.py /private/synthetic/actual-borrow-observation.json
```

No actual positive capture, SQL, service, native owner or restart has been run
by this commit. Pure mapping tests use explicitly artificial manual specimens,
never label them production captures, and keep the oracle's actual fields null.
All initial checker errors, actual pipeline failures and unsupported inputs
will be retained without relabeling. Parent author validation is not this
independent signoff. Production, real funds, capacity and HA remain unapproved.

Deployment is unnecessary: this is an offline reference addition, no schema
or API migration. Rollback reverts these new checker/docs/tests in a new commit
and retains original evidence; it cannot delete published authority or funding
history, enable public borrowing or downgrade a capability-marked database.


## First executed mapping controls

The adapter/contract were committed at `9028e4f`, then the eight manual and
adversarial tests at `e04ac7b`, before execution. The first and only pure batch
ran on CPU4/Python3.12 at 2026-11-17T14:41:40.630232–40.739418 UTC,
wall0.109186 seconds, eight tests passed with ResourceWarning treated as error.
No actual observation, SQL, native scope or service was involved. All source
hashes, exact command and original stdout/stderr are retained in
`evidence/reviews/credit-actual-capture-independent/`. The actual gate remains
PENDING; these mapping controls do not upgrade it.


The later content extension `e3e9c75` additionally checks original pool-funding
capital/pool legs, funding receipt identities, funded capital against gross
pool plus principal, local opening allocation/funding claims, immutable static
certificate/capability identities and artifact source/loaded-code map digests.
A balanced forged capital leg is rejected even after recomputing its self hash.
These are retained-content checks, not an assertion of source authenticity or
that archived executable code matches a live binary. The extension's first
pure batch ran 2026-11-17T14:43:50.659670–50.781143 UTC on CPU4/Python3.12,
10 tests passed in wall0.121470 seconds; original earlier8-test raw is retained.
Actual capture, SQL origin and native/COMMIT/restart evidence remain pending.


## First actual BORROW: independent SQL and financial reference

**Scoped PASS**, not full M3 acceptance. The author fixed source/tests at
`3e3e8133d9fc8e734a6fb244bf989d7010aed23e` and retained first native BORROW
execution evidence at `1156ba1`. The independent checker was committed before
execution: capture adapter `9028e4f` and extensions through `556628e`, then the
independent original-SQL reader `43d2fe4`/`b3885bb`. No production calculator,
exporter, serializer, risk transition or replay function was imported.

On 2026-11-17T14:48:21.904964–22.001178 UTC the first independent SQL batch
ran once on CPU4/Python3.12, wall0.096219 seconds, exit0, ResourceWarning error.
It reopened the actual retained synthetic DB, not a backup or fabricated
specimen, with mode=ro, query_only, SELECT-only authorizer and one read snapshot.
The author had closed all handles and left the DB after BORROW `loan-1`, before
any repayment. There was no new producer/native write or injected failure.

The independent reader selected the original source, inbox, intent, credit
receipt, journal and decision/market/policy/artifact rows directly through
standard sqlite3. They matched the original 220089-byte export byte-for-byte
as JSON structures. Original file SHA256 is
`c3cfc2238d40225a0fd0c9408abcdf0005a298c50fa8876b6af92d309b03b2c7`;
the same original bytes without the final newline have digest
`3c97bea652c42d57706a4fb260c56553a1b51dc9f0d4499d49a7e54989866a1e`.
The exact copy and original raw checker stdout/stderr/command/source hashes
are retained in the independent evidence directory.

The original opening state was USD100, no BTC/debt, funded poolBTC1, account
version1. The fixed local/global allocations are .5/1 BTC; actual account and
local limits are .5 BTC. The .4 BTC borrow is feasible under the frozen manual
M1 math and actual limits. The actual result is:

| Item | Independently expected and observed |
| --- | --- |
| Customer USD/BTC | 100 / .4 |
| Principal / interest | .4 / 0 BTC; liability ledger −.4 / 0 |
| Pool / principal receivable | .6 / .4 BTC |
| Accounting equity / discounted collateral | 100 / 132 USD |
| Gross debt / risk equity | 40 / 92 USD |
| IM / MM / open-order reserve | 8 / 4 / 0 USD |
| Available margin / E÷MM | 84 USD / 23 |
| Next conservative portfolio quote | .26 BTC; actual remaining static budget .1 BTC |
| Account version | 1 → 2 |
| Borrow journal | customer +.4; liability principal −.4; pool −.4; receivable +.4 BTC |

All three original ledger events, eight postings and seven materialized
balances were independently checked: contiguous sequence/ordinal, original
hash chain, sealed events, zero sum per currency per event, and full balance
reconstruction. The original prehead balances match retained gross prestate;
current post cash, liability ledgers, pool and receivables match the independent
transition and actual liability rows. Live positions/orders/frozen balances,
limits, halt and liquidation state were selected independently and agree.
Actual interest cash was additionally queried through the journal and remained
0; the content payload alone still does not claim to observe that balance.
The actual original financial rows were collected once more for durable raw
review at 14:50:02.373698–02.428946, wall0.055225 seconds, zero logical changes.
That fixed nine-table allowlist never reads writer-fence, owner or auth/nonce
rows. This collection is not a native or financial-test rerun. The original DB
stays private; only synthetic selected rows are public.

The three actual retained checkpoint calls use the author's **fixed injected
synthetic exchange clock**, 2026-11-17T00:00:00Z, rather than the current wall
clock. This case therefore proves neither live-market TTL enforcement nor
wall-clock regression/recovery. Actual physical COMMIT time remains null.
The first reader's content subreport intentionally retains its provenance
PENDING label: the surrounding independent SQL observation closes only original
SQL selection/reopening and financial correctness for this one committed case.
It does not independently prove the producer's prior source+PENDING COMMIT,
native owner authentication, FIFO timing, a single financial COMMIT boundary,
unknown-result recovery, process restart, crash durability or replication.
Those remain separate execution/fault gates. Multi-product M3, public enablement,
real funds, performance, HA and production approval remain **NO_GO/PENDING**.

No initial red or retry occurred in the independent actual SQL batch. No native
run was repeated to obtain this result. Rollback/deployment boundaries above
remain unchanged. The private original database must not be published or
modified as part of integrating these reference/evidence-only commits.
