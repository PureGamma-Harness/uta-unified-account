# Fixed-basis interest accrual kernel — pure reference milestone

`uta/interest_accrual.py` computes deterministic accrual proposals. It does not
read a clock, access storage, post accounting entries, run a scheduler or grant
any financial permission. Existing `CreditService.accrue_interest` recognizes
an explicitly supplied amount; it does not derive that amount from a rate or
period. The current V2 certificate still requires `new_interest_rate="0"` and
does not support new accrual after activation. Those behaviors are unchanged.

## Scope and chosen rules

The policy identifier is `UTA-INTEREST-ACT365-PPB-CARRY-v1`. It is a local,
unactivated policy, not a claim about exchange charging practices. No authorized
exchange event/rate history closes those external evidence gaps. The arithmetic
is for spot-loan principal in one currency's integer minimal units; it provides
no Isolated, Cross, PM, collateral, futures-funding or trading activation.

- Principal and booked units are exact Python nonnegative integers below10^38. Scale
  is an explicit0–18 currency descriptor. No decimal/float coercion occurs.
- An approved caller would supply a versioned simple APR, represented as integer
  parts per billion, between0 and1,000,000,000 inclusive. The100% APR cap is a
  local model bound. Higher rates and other day-count conventions are refused.
- Timestamps are explicit integer Unix nanoseconds in0..2^63−1. One command
  covers `[start,end)`, with positive elapsed time no longer than366 days. Rate
  coverage includes every instant before end; equality with its `valid_to` is
  allowed. A leap year's366 actual elapsed days still uses a365-day denominator.
- `D = 365 × 86400 × 10^9 × 10^9`. For constant principal and rate over a segment,
  `N = old_carry + principal_units × annual_ppb × elapsed_ns`. Book `N // D`
  minimal units and retain `N % D`. Interest never enters principal implicitly.
- The cursor must be contiguous. Rate changes require explicit versions and a
  split at the effective boundary; an already used rate ID/version cannot change
  payload. Principal changes are separate commands at the already accrued cursor.
  Their carry remains intact. Zero rate or zero principal never erases it.
- `cumulative_booked_units` is a lifetime accrual counter, not unpaid interest.
  The actual ledger owns interest repayments. Until an integration exists, the
  kernel's extra unbooked risk amount is only `int(carry > 0)` minimal units,
  to be added conservatively to actual gross unpaid interest. It is not cash,
  available collateral, permission to borrow or a replacement debt balance.

Every valid new command includes an original business reference, expected sequence
and state hash. The book retains immutable receipts and rejects conflicting reuse,
stale checkpoints, gaps, overlaps, bad rates, overflow and unknown reference queries.
An identical historical retry returns its original receipt and does not rewind
the current cursor. At4096 new receipts the bounded in-memory book refuses another
new command, while original retries remain queryable. This is a single-threaded
pure model; no result proves durable idempotency, single-writer fencing or restore.

`loan_id` names an accrual stream. A future integration with the current aggregate
`uta_liabilities(account_id,asset)` must enforce one active stream per account and
asset and accrue its aggregate principal. Creating a new stream must not reset
fractional carry when principal becomes zero or a customer borrows again. Loan
closing, fractional-interest collection/waiver, stream migration and compounding
remain unsupported rather than silently dropping or charging residual fractions.

## Human calculations and first execution

| Case | Exact lifetime interest, in currency minimal units | Booked / carry / extra risk |
| --- | --- | --- |
|100 units,5% APR, half fixed year|5/2|2 / D/2 /1|
|365 units,100% APR, one day|1|1 /0 /0|
|1 unit,100% APR, one day|1/365|0 / D/365 /1|
|1 unit,100% APR,365 daily segments|1|1 /0 /0, same economic result as one interval|
|365 units,10% first half and20% second half|219/4|54 /3D/4 /1|
|365→182 principal, each half year at100%|547/2|273 /D/2 /1|
|365 units,100% APR,366 elapsed days|366|366 /0 /0|

The first author run used fixed code `c507e0b458f24d2434ed2c24df597ba171113d3c`:
16 tests, zero failures/errors/skips, CPU2,204,185,580ns before result serialization.
The same process recorded the actual import path and every63 runtime blob plus the
test file before execution, and verified unchanged hashes afterward. SQLite
connect, process creation and signal functions were hard-mocked during the test
scope; all those call counts were zero. The launcher's read-only Git metadata
commands precede those mocks, so this is not a claim of zero tooling subprocesses
for the complete launcher. Only `uta` and `uta.interest_accrual` product modules
were imported.
The original driver, raw test streams and manifests are retained under
`evidence/interest-accrual/first-pure/`. They are synthetic arithmetic metadata,
not customer data. This is not a throughput measurement or full-suite result.

Recompute the focused cases from a full checkout of the code commit:

```sh
taskset -c 2 timeout 10s python -B -m unittest discover \
  -s tests -p 'test_interest_accrual.py' -v
```

Select an available CPU on another machine and record the change. Use a new output
directory for a new run; do not overwrite the retained first evidence. The archived
driver describes its original path and commit and is not a generic rerun launcher.
Independent Fraction standards were frozen separately before consuming this code.
Their actual differential result is a separate milestone and is not implied by
the author's16 focused cases; consult that independent commit and its first raw.

## Required financial integration and rejection boundary

The next integration must add an independently reviewed, versioned native event
kind rather than widening the current V2 zero-rate certificate. An authoritative
account writer must atomically commit the unique interval/reference, previous and
new cursor/carry, receipt/hash, liabilities projection and journal. For a positive
delta `i`, the existing account definitions prescribe same-currency legs:

| Account | Signed minimal units |
| --- | --- |
|`system:credit-interest-receivable`|+i|
|`liability:interest:{account_id}`|−i|

There is no customer-cash or principal movement. A zero-unit segment still needs a
durable checkpoint and reference, without a fabricated nonzero journal posting.
Incurred interest may exceed a borrowing limit: record the obligation and restrict
new borrowing, rather than dropping interest because credit capacity is exhausted.
Actual unpaid interest and gross principal remain distinct; held collateral is
not netted against them. The additional carry reserve must be counted once.

The writer must obtain authoritative principal changes and approved rate history,
validate clock/source versions and use the account's real fencing token. The pure
kernel cannot identify a legitimate current time or prove that a supplied segment
has complete history. Scheduler retries must query the original reference first
after an unknown commit. Restored state must resume the exact prior cursor and
carry; reconstructing only rounded ledger interest is insufficient. Concurrent
schedulers, rate rollback, pauses and missed periods need independent integration
tests and a unique active account/asset stream constraint.

## Deployment and rollback

This milestone requires no database migration or runtime configuration. Leave
existing credit capabilities and all service/API wiring unchanged. The pure
module can be evaluated offline against synthetic histories. Removing its import
or reverting this isolated module/tests reverses the milestone; retain historical
rules and first evidence. There is no scheduler to stop or financial effect to
compensate. If any accrual journal/source row is observed from this milestone,
stop and investigate that boundary violation.

Real accrual activation requires a new native schema/capability version, approved
rate control plane, account/asset checkpoint migration (including residual carry),
actual transaction/restart/unknown-result tests, reconciliation and explicit release
approval. This reference provides none of those approvals.
