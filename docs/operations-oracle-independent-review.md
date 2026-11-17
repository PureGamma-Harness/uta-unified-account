# Independent managed operations oracle review

Reviewed origin: `8e1de5c4d79e9a45f638b67b65cbed87b7ad3d09`.
The operations integration, root checkout and old long-running soak were not
modified. No job longer than the existing four-second smoke was started.
Production remains **NO-GO**.

Two acceptance-oracle gaps were concretely reproduced. These are validation
coverage defects, not customer API vulnerabilities or evidence of real money loss.

1. `ManagedSoak.verify(full=True)` does not check the exact three-account set or
   the credit account's promised 1,000,000 USD genesis cash. A deliberately
   drifted **public** `ShardRouter` bootstrap deposited 1 USD extra into the
   credit account and created a fourth empty account before normal managed
   sealing. Cold `verify(0, full=True)` still returned `golden_passed=true`.
   Actual credit USD was **100000100000000 minor units** and the account set
   contained `managed-soak-alice`, `managed-soak-bob`, `managed-soak-credit` and
   `unexpected-fourth-account`. The six genesis journal events and complete
   per-currency posting conservation remained valid. Balanced postings do not
   establish the declared budget or participant identities. Separate tests keep
   the extra-USD and extra-account cases independent; the combined case retains
   all four accounts and the wrong cash, rather than removing them to pass.
2. Full audit checks decision joins to artifact/policy rows but does not hash
   their contents. In a memory-only reconstruction of the committed historical
   synthetic smoke10 snapshot, baseline `verify(3, full=True)` passed. Changing
   an artifact manifest or policy payload to the valid JSON object `{}` left its
   old content ID inconsistent, yet `golden_passed=true` persisted. The fixture
   reconstruction deliberately contains no installed immutable update triggers;
   it is a disclosed archive-fault test, not a normal write path. Its omitted
   `ledger_assets` rows are restored to the documented USD/BTC scale 8 before
   either baseline or negative inspection. Missing archive references and
   changed market payload digests already fail and serve as negative controls.

The original source itself creates the documented three accounts and deposits;
this review does not claim an ordinary run currently manufactures the drift.
The gap is that its independent final golden audit can accept off-contract
genesis data or damaged evidence that it claims to check.

Other reviewed boundaries had no identified blocker: long-run qualification
requires exact clean HEAD, complete source manifests, matching runtime versions,
zero-typed outcome counters, preserved sidecars/log hashes and explicit opt-in
before job state is created. Its local OS owner/report producer are trusted;
these checks do not sign reports or grant production/duration approval. Command
recovery queries the original CID before an identical retry, records only real
terminal receipts and independently observes partial/close matching. Faults
signal actual PID/birth identities and require a newer fencing generation.

ROAPI checks roles/account scope before querying, filters private account rows
before pagination, projects only customer ledger postings, and reads one SQLite
snapshot. Event sequences are shard-global and may have private gaps; the fixed
`until` cursor is drained before observing a new range. Account-version and
file/stream identity mismatches require rebuilding. Multi-request snapshots do
not have a lease; market/config changes require client comparison. In-place
administrator rollback and whole-machine cloning are explicitly outside the
stream identity guarantee.

Bounded checks at the reviewed origin: all **19 managed view tests passed**;
the existing real TLS/worker-and-parent restart smoke passed with configured
duration **4 seconds** (5.221 seconds wall time). No full-release validator or
long-run qualification evidence was produced by this review.

Reproduce the independent characterization tests with:

```sh
python -m unittest discover -s tests -p test_managed_soak_oracle_reference.py -v
```

These tests initially assert the incorrect origin behavior to preserve its
reproduction. A subsequent tool-only fix must require rejection of the unchanged
drifted/faulted inputs, retain correct budget/matching/debt controls, and verify
content IDs with independent hash/JSON checks rather than calling production
financial replay as its sole oracle.
