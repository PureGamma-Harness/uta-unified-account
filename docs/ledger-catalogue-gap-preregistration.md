# Ledger catalogue gap: independent preregistration

Status: NOT_RUN. This is ordinary correctness validation of a persisted classic
ledger, not an assertion about malicious OS users or a production approval.
Source is fixed at `4ad58b2169b02f8982a1cbef8722b79d705d60c8`.

The original `DurableLedger.verify` checks integrity, current declared foreign
keys, ledger version/scales and exact protection triggers. It then selects
postings separately for every declared event. The question is whether an
offline restored catalogue that lost the event foreign key can hide an orphan
posting while preserving every valid event, materialized balance and trigger.
This is a hypothesis until the separately authorized actual run.

The independent case uses public `Database` and `DurableLedger` constructors
and `post` calls. USD has scale2. Event `manual:1` transfers1250 units from a
to b; `manual:2` transfers300 from b to c. Four postings project exactly to
a=-1250, b=950, c=300. A separate literal JSON/hash calculation checks both
original journal hashes and all original rows; no production hash/replay
function supplies expected values.

After all public connections close, an offline synthetic fixture reconstruction
rebuilds only `ledger_postings`. It removes only
`sequence REFERENCES ledger_events(sequence)`, retaining the asset foreign
key, column/NOT NULL shape, ordinal CHECK, primary key, original four rows and
every original trigger definition. This is deliberate fixture mutation before
verification; neither verifier nor live authority has a guard disabled. The
script then inserts one additional row `(99,0,'orphan','USD','1')`. The sealed
event trigger's scalar lookup is NULL for99; with the missing foreign key the
offline insertion may succeed. This is not a financial command or a customer
operation.

The proposed one-shot run uses Python3.12 on CPU4, a new private0700 directory,
one new unmanaged SQLite file and no processes/services/workers. Root must
authorize the exact committed driver SHA first. A14-second process alarm and
strict whole<=15-second result bound cover source guards, public setup, offline
reconstruction, reopen, original verification and evidence. There is no retry.
The original DB and every raw result remain in the new directory, even on a red
control or budget failure. No original job, frozen checkout, existing DB, clock,
affinity or signal is changed. No test or production function is monkeypatched.

Required actual observations are: original verify=2; independent manual rows,
hashes and balances match; original FK edges exactly two; post-reconstruction
event FK absent but asset FK retained; all original rows and triggers unchanged;
table columns/PK unchanged; one orphan is actually present; integrity_check=ok;
foreign_key_check has no violation for its remaining declared constraints;
original reopened constructor and default verifier outcome; and unchanged
logical catalogue/rows across that original verification. If original default
verification accepts two events, record a reproduced integrity-detection gap.
A refusal is a non-reproduction or another-stage result, not a rewritten PASS.

No fix is included. If reproduced, propose minimal persisted-catalogue
validation of the expected columns, primary keys and foreign-key declarations
before either default or opt-in replay. Unsupported catalogues must receive a
typed refusal without repair, schema migration or rewriting original failures.
Root and another group must review any fix; this independent observer cannot
sign off its own later implementation. The separate ordered-postings R&D
branch remains unmodified and is not imported by this experiment.

