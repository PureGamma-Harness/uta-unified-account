# Independent managed operations oracle review

Reviewed origin: `8e1de5c4d79e9a45f638b67b65cbed87b7ad3d09`.
The operations integration, root checkout and old long-running soak were not
modified. No job longer than the existing four-second smoke was started.
Production remains **NO-GO**.

## Fixed-budget correction

Original incorrect behavior and all nine characterization tests are retained at
`6fc64909fa702afad0ceab7189d7b29e5328eaca`, directly after the reviewed tool SHA.
The fixed-budget correction `e2e19bd29079d4b9008c5147fdf3dab517c46ec9`
requires the exact three account IDs and USD/BTC
scales, compares every ledger owner/asset against a hand-derived closed gross
budget, and checks the complete debt projection plus one initial pool funding,
one initial loan and exactly one two-satoshi repayment per completed round.
The credit account's unchanged 1,000,000 USD, custody obligations, funded capital,
pool cash, principal receivable, customer principal and fee ownership are all
included. No production fee, risk, credit or replay helper generates expected
money. Existing complete posting conservation/projection and business counts
remain required. Extra accounts or cash are rejected and retained for evidence;
the verifier never removes them or adds a compensating top-up.

## Archived-content correction

A separate tool-only correction checks every stored market, artifact and policy
object, including all decision-referenced objects, with independent standard
library JSON and SHA-256 operations. Stored bytes must be a canonical JSON
object without duplicate keys or nonfinite values; content IDs must equal the
appropriate `market:`, `artifact:` or `policy:` prefix plus the exact-byte digest.
Market `content_digest` must also agree. Duplicate identities are ambiguous and
fail. Existing decision joins still reject missing/rehashed objects whose old
IDs remain referenced; business counts and journal/projection checks remain in
place. Corrupt unused archive rows are retained and rejected as well.

The verifier never evaluates archived code, invokes a production financial
replay, rewrites an ID/reference or repairs a payload. These local unsigned
content checks establish internal consistency, not a signature or protection
against an administrator consistently rewriting all history. The historical
findings below describe the immutable origin preserved in `6fc6490`.

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

The original nine tests in `6fc6490` assert the incorrect origin behavior to
preserve its reproduction. The current **17 reference tests** instead require
rejection of the unchanged drifted/faulted inputs and retain valid budget,
matching and debt controls. All 17 passed, along with the existing **5 managed
soak tests** (each actual workload configured for four seconds) and **9 release
qualification gate tests**. The five-test suite took 10.126 seconds total; no
individual long workload was started. `git diff --check` passed.

Only benchmark/oracle tools, tests and documentation changed. No `uta` runtime,
operations integration worktree, root checkout or old long soak was modified.
These source changes require a newly frozen candidate and a fresh complete
validation report before the long-run gate can admit any future >60-second job.
This review does not produce that report or authorize a long/production run.
