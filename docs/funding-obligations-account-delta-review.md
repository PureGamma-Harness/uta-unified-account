# Funding obligations: independent account delta review

**CODE CLOSED for FUND-OBL-001/002 at `90e81daa7b7cb398664c1dadb3a0d943e45321d6` only.**
This is a static account/ledger review, not SQL acceptance, execution permission,
or production approval. All target import/compile/SQL/test/thread/native/proc/CI
attempts in this review are zero. Independent risk cross-review and a separately
frozen runner/root execution grant remain required.

The reviewed tree is `11be4d96446afd67cfdd36e461d0d786539ecad5`, sole parent
`901700637b3bb329cbb5729227e5b654dd8a00b6`. This delta report follows and preserves
review `ed1724a43b667d039d36d87483589bfc4b0fd162`; the older source and its three
NOT_RUN preparation files remain immutable records.

## Correction to the previous trigger description

I omitted the outer publisher's coverage checks in the previous review.
`uta/service.py:693` rejects removal of a symbol present in any position or live
order, and lines699–705 protect funded asset and gross-liability quotes. Therefore
the previous proposed public sequence “live BTC positions, publish USD-only,
then apply” is **not reachable through that publication API**. Its asserted normal
public-path reachability is withdrawn; no target failure was ever executed.

A cash-only account with no BTC positions/orders can legally publish USD-only.
The revised capture example uses that state and the snapshot's actual SHA. A
scheduled BTC boundary still needs its approved mark; absent data must remain
WAITING_DATA rather than fabricate a zero-rate or historical position cut.
For current live-BTC partial data, the revised test first expects the real
publisher to reject, then supplies a typed partial snapshot only to the helper
inside a read snapshot. That is a decision negative control, not a durable apply
or corrupted-market recovery integration test. The latter remains OPEN.

## Delta closure

FUND-OBL-001: `FundingObligations._require_mark` (lines319–325) checks supported
linear product/multiplier/margin rules before raising the specific
`funding_required_quote_unavailable` for a genuinely absent mark. Capture calls
it after native fresh-market loading and before the direct symbol lookup or cut
insert. Its existing ServiceError branch records WAITING_DATA and releases the
claim. Invalid product/rule inventory is not relabeled as a missing quotation.

FUND-OBL-002: `_check_current_quotes` (lines327–353) first calls native `_risk`.
Only `risk_unavailable` with an exact native `PortfolioError`, one of its precise
missing-price messages, and an actually absent corresponding map key converts.
The instrument also has to be in current positions and pass `_require_mark`.
An unsupported collateral/borrow rule remains a financial rejection. The live
order path requires native `market_incomplete`, an exact one-argument `KeyError`,
the absent instrument key, and a current live order referencing that symbol.
All other exceptions are re-raised; neither all ValueErrors nor every
`risk_unavailable` becomes retryable. This does not prove recovery for every
market-expiry/interleaving cause.

The new preflight runs for each actual cut participant at `_cash` lines504–505,
inside the existing apply SAVEPOINT and before capital or customer postings.
The exact new data reason is added to WAITING_DATA at line464. Existing financial
rollback, full verification, real supervisor, final fresh-market comparison and
final claim observation remain unchanged. A successful receipt/APPLIED and the
cash, risk state, versions and command remain in the original single writer
transaction; an expected application failure rolls back staged financial work
before recording its waiting/review result. Storage/COMMIT failure still means
UNKNOWN, not a proven durable error result.

Current requirements are derived from current positions/orders/assets, not the
old cut symbol. Real close execution deletes flat position rows
(`service.py:988`); terminal close orders are absent from `_live_orders`.
Consequently the legitimate post-close USD-only case can apply old frozen BTC
funding while evaluating current cash risk without an unnecessary BTC mark.

## Static inputs and planned manual evidence

All 66 canonical regular input files match both their physical SHA/length pins
and Git objects at the reviewed commit: 1,414,749 bytes. The 63 other UTA Python
files are byte-identical to 901. The changed module is 63,141 bytes, SHA256
`13e3f7d35b2aeefdb8bb5852280bb2cb65e40c3a62858ec4cc37b4fc3eb51e97`.
Manifest SHA256 is `8653d8976cc7b3191fe14600a21579aac2de8cea107ce1b40d9b42228fecde98`;
plan SHA256 is `4c5b959b12437f53b38474cdd112eabb5529151c93a937f17d951e2fd667e36f`.
All three `-901-NOT_RUN.json` copies match the corresponding original Git bytes.
AST parsing confirms the original six fixed method names; it executes no target.
The artifact's fixed module list, loaded function/default/closure/constant
serializer and exclusions are unchanged; the two added helpers fall under the
existing local class-method coverage. Source hashes alone are not loaded evidence.

The revised missing case defers one initial paired trade until after complete
quote restoration: six populated fixture matches plus three method-local matches
still total nine independent-scenario matches/eighteen fills. Two empty
capability cases keep the total at nine fresh scenario DBs. Five applies/eight
tasks/three outstanding remain the planned counts, not observations.

Independent arithmetic is unchanged: 16 deposits, 18 fill journals, 11 funding
journals and one intentional orphan total 46 journals. Fees across the seven
populated cases are .08+.08+.08+.14+.08+.18+.08=.72; custody is -15001.
For the changed-position example, opening fees leave both accounts999.96; a real
close at101 adds PnL(+1,-1) and fees(.05,.05), yielding1000.91/998.91. The frozen
cut100/rate.01 cash(-1,+1) then yields999.91/999.91, with no new fill and fees.18.
These are manual planned oracles, not a passed execution or throughput report.

## Remaining gates and recovery

The claim guarantee is only a final observed trusted-clock/generation check
inside the serialized writer. Receipt/task/command/event writes and physical
COMMIT/fsync follow it; there is no physical COMMIT-before-lease-deadline proof.
Pending funding is not integrated into order, withdrawal or transfer reservations.
Production timer, authenticated operations/custody, exclusion of old binaries/raw
writers, managed fencing/HA/replication, crash and real-clock concurrency proof,
capacity, and human financial launch approval remain OPEN. Customer funds,
insurance and ADL activation remain NO_GO.

No deployment or data migration occurred. The author runbook continues to allow
only a fresh synthetic authority. Before any later execution, freeze exact
runner/selectors/inputs/resources independently. For rollback stop explicit
calls and preserve all obligations, cut/claim/command/receipt/journal/event
records; do not delete capability tables, forgive unpaid obligations, rebind old
code, or fall back to the mutually exclusive old funding prototype. A code
rollback cannot silently reopen an authority whose archived artifact differs.
