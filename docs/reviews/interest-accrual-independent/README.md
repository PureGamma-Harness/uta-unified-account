# Independent interest-accrual reference preparation

The manual rational cases were authored before importing the candidate kernel.
The oracle uses `Fraction` for each principal, annual-rate fraction and elapsed
time fraction; it does not reuse the candidate's integer arithmetic or state
transition functions. The policy is this system's experimental rule, not an
assertion about any exchange's billing periods or current interest rates.

The agreed v1 specification uses integer APR parts per billion in0..1e9,
ACT/365-fixed nanosecond intervals, simple interest on explicit principal and
fractional carry. A segment duration must be positive and at most366 days.
The carry denominator is `365 * 86400 * 1e9 * 1e9`; rate changes retain carry.
Book and principal representations are below1e38 units, timestamps at most
2^63-1, and intermediate integer arithmetic is bounded below2^256.

The booked counter means historical accrual within the pure model. It does not
mean current unpaid interest. Positive residual carry requires one extra minimum
unit of conservative risk reserve; this reserve must be combined with actual
unpaid liabilities by a separately accepted financial integration.

The future differential check must also exercise contiguous intervals, rate
coverage/version identity, principal changes at the cursor, CAS, exact replay,
changed-payload conflict, receipt capacity and rejected-input state preservation.
The numerical oracle alone does not prove those lifecycle properties. Product
API mapping will be added only after a fixed candidate commit is supplied.

Existing V2 policy requires new interest rate0 and prohibits new accrual after
activation. It remains unchanged. No AuthDB, financial DB, scheduler, source,
PENDING row, service, worker, public route or active long-run file is used here.
This preparation requires no deployment or data migration. Rollback removes
these independent reference paths; preserve manual cases and any first failure.
No production, full-H0, capacity or real-funds acceptance is claimed.
