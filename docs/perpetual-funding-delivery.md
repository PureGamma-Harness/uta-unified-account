# Local perpetual funding settlement delivery

This is an audited local prototype for one authority, synthetic USD settlement,
Cross linear perpetuals with multiplier1. It adds no REST route, background
worker or default product activation. The existing61 UTA modules are unchanged;
the two new modules provide exact arithmetic and a local transactional adapter.
It is not production funding or a completed phase-one exchange release.

Funding uses signed quantity, multiplier, mark and signed rate, with explicit
toward-zero currency rounding and separately recorded waived subunits. Period
identity is symbol plus scheduled UTC label; it is not a claim to reconstruct
past holdings. Missing trusted past-boundary evidence rejects late settlement.
Known command IDs return their original receipts; conflicting parameters,
duplicate periods and reused capital evidence reject without extra postings.

Rounding deficits require already deposited, segregated treasury funds and a
unique capital proof. Negative system capital is not minted. Mandatory customer
debits remain cash deficits rather than fabricated borrowing principal. The
same transaction invokes the existing risk supervisor: confirmed cancellations
and a reduce-only plan are persisted, with no invented liquidation fills.
The accounting policy remains subject to human financial approval.

The unique first arithmetic run passed3 methods; independent RAWb9aabc07
verified its originals. Corrected SQL control2326106 passed3 methods over5
fresh scenario authorities. Across those namespaces,6 matches/12 paired fills,
32 journals and3 funding commits were confirmed. Business trade IDs repeat
between scenarios, and those commits use one calendar period label; these are
not6 globally unique live trades,3 distinct UTC periods or throughput evidence.
The deliberately orphaned-journal scenario correctly fails funding verification;
the other four scenarios reconcile without an orphan.

Independent RAW0e2fbd3a bound32 private originals/3960837 bytes and directly
decoded the five sealed databases using a bounded standalone byte reader.
All five WAL files were empty and current main-file headers/pages were checked.
Journal chains, per-currency balance, positions keyed by account and symbol,
deposits, matching/fills, exact fees/PnL, funding receipts, actual treasury.01
and the cancelled/replacement RO orders were independently recalculated.
The reader's initial DDL-parser error and corrected reader are preserved as
review-tool history, not a rerun or failure of the target settlement.

The actual caller observed outer exit0/reap and both EOFs in2.162771041s.
Target/drain1.904235790s, inner-with-oracles1.644386558s and selected tests
1.308923454s are separate intervals.133 observed connection handles were closed,
cleanup0. Logical file-size observations do not prove a continuous disk quota.
Full databases, source capsules, nonces and original archives remain private;
public evidence is limited to checked exports, finite summaries and hashes.
First integrated CI for this delivery is pending.

## Deployment and rollback

Deploy only to a new synthetic local authority using the frozen source, policy,
market and approved command references. Existing-authority migration, managed
writer fencing, replication and production credentials are unsupported. Do not
hot-swap a running authority or relax artifact/schema checks to open it.
The explicit once entry requires a fresh exclusive namespace; do not reuse the
sealed run paths or rerun an unknown outcome under a new business ID.

Rollback stops the invocation and preserves receipts, journals, positions and
all first evidence. Confirm the original command outcome and reconcile before
writer handoff; do not erase confirmed effects. Durable DUE scheduling and
unsettled-obligation persistence, historical catch-up, stale-market failure
handling, commit/crash injection, multi-currency settlement, ops approval,
custody, HA, capacity and real-funds release remain OPEN.

Earlier CODE plans keep their original NOT_RUN preparation fields. The separate
first-run records and independent reviews establish only the finite executions
above; no exchange's undocumented precision or capital policy is asserted.
