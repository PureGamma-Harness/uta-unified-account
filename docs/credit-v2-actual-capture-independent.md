# Actual credit capture: independent verification contract

Status: **PENDING_ACTUAL_CAPTURE**. This work is separate from production
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
