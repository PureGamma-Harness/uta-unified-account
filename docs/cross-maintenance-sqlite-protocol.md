# Fresh SQLite maintenance-boundary validation protocol

Status: **CODE_ONLY / NOT_RUN / zero SQL attempts**. This is a proposed single
bounded run, requiring an independent code review and root's exact source and
manifest authorization. Neither the manifest nor command-line parameters grant
execution permission. The completed pure result is separately sealed at
`ca0f37bf`; its original private files and its independent RAW closure are
retained. This protocol does not reopen or modify that scope.

## Model and execution boundary

The financial runtime is the 61 UTA files of corrected source `402c784`, with
only its already reviewed 14-line strict-MM service addition relative to PR35.
The three authorities use real `Database`, `ExchangeService` and the original
`Matcher`. Native matching, two account fills, journals and match receipts share
the existing SQLite transaction/savepoint. No method, function, class, native
SQL connection or clock is replaced. All orders use the existing limit-order
API and default fee rate 0.0004. The caller is one synchronous process, on CPU1,
without workers, network, auth database, process probes or auxiliary children.

Each fresh authority has explicit, persisted Cross product/risk configuration;
USD settles at one with factor one, contract multiplier is one, positions are
linear perpetuals, eligible hedges and new borrowing are absent. Isolated, PM,
spot, options, inverse products, external execution ingestion, HA and production
activation are outside this run. REST/WebSocket routing and permissions do not
execute in this functional native-API scope.

Independent CODE review of the original prepared source `fafd5959` found one
proof-completeness gap: the cancellation allowlist compared A and B account
rows without comparing the complete account set. It did not establish that
matching actually creates an extra account. The corrected assertion compares
the complete new account map with the complete prior map after only A's one
version increment; it rejects any added, removed or otherwise changed account.
The exact prior plan and manifest are preserved as
`sqlite-source-plan-fafd595-NOT_RUN.json` and
`sqlite-source-manifest-fafd595-NOT_RUN.json`, with the static finding separate.
The prior source had zero SQL/target attempts and remains NOT_RUN, not RED.
All other case code, rollback rows/schema, financial examples, native API
operations, fees, margins, runtime files and resource budgets remain unchanged.

Only three new `.sqlite3` files may exist under the new private business
directory. The full 61-file source plus two control scripts is pinned to Git
blobs and copied into a read-only mini checkout before import. The original
source and mini copy are rechecked after execution, and imported UTA origins
must belong to the frozen mini. This is a trusted fixed program, not an OS
sandbox or hostile same-UID isolation.

## Exact manual cases

| Authority | Native setup and intended result |
| --- | --- |
| MM equality and second-leg rollback | USD8; ETH mark/execution 10, BTC 100, IM=MM=.1. A deposit 11.04400009, B 1000. Real ETH trade A+1/B−1 charges .004 each, leaving A cash11.04000009 and B999.996. A BTC sell−1 admission projects equity11.00000009 > MM11 and is accepted, with B's opposing buy accepted. A genuine fresh market publication changes only ETH mark to9.9999999. A BTC fill then has equity=IM=MM10.99999999, availability0 and must reject. |
| Valid IM equality with lower MM | USD8; BTC100, IM.1/MM.05. A deposit10.04, B1000. Actual matched BTC A+1/B−1 charges .04 each; A cash/equity10, IM10, MM5 and availability0 must remain accepted. Original reduce-only closing orders then match, leaving no positions, A9.96, B999.92 and systemfees.16. |
| Cumulative fee across real partial matches | USD2; BTC mark/execution1, IM.1/MM.05, price tick.01, quantity step.1, minnotional.1. A deposit.11 sells−1 against B's distinct buy orders+.4 and+.6; B deposit10. Two matches charge A [.01,0], B [.01,.01]. A finishes cash/equity.10, IM.10, MM.05, availability0; B9.98 and systemfees.03. The matches reflect the two original orders and serve fee validation only. |

There is **no perpetual funding API in this runtime**. The funding terminology
found in `uta.credit` concerns external credit-pool capitalization, not perpetual
funding fees. The first case uses only the existing real `publish_market` API;
it never fabricates a funding charge or writes cash/liabilities with SQL. Actual
funding/settlement functionality remains an explicit product acceptance gap.

In the first authority, a direct `apply_fill` known rejection first demonstrates
that strict-MM failure has no durable effects. A separate real matcher attempt
then reaches buyer B first and seller A second. A bounded read-only Python
profile hook matches the exact native `_apply_fill` and strict-guard code
objects, observes B returning a FILLED order before A enters, and records A's
actual projected equity/MM equality. It changes no arguments, code objects or
return values, and is removed in `finally`. Its overhead is not a performance
measurement.

The matcher must roll back the buyer's first-leg effects and all failed seller
effects, then apply its existing cancellation of only the rejected A order.
All main application tables and schema are captured. Exact differences are
permitted only for A's one cancellation version, its order status/version and
one `ORDER_CANCELLED` event with the correct reason. All balances, journal
events/postings, positions, fills, matches, risk decisions, policies, configs
and archived quotes must be identical across the failed match. This is not
described as a globally unchanged database, because the cancellation is real.

After A's cancellation, its available margin is exactly10.04. A distinct fresh
BTC order at that reserve equality must reject without any durable effects.
The accepted original ETH order and fill IDs are each replayed once, without
additional effects; a changed-quantity reuse of the original fill ID must reject
with `idempotency_conflict`. B's unfilled BTC order is explicitly cancelled
through the existing API before final verification. These known business
outcomes are planned assertions, not retries after a harness failure or an
unknown execution result.

## Evidence and stopping rules

The planned committed result is five unique authority-qualified matches and
ten paired fills across three authorities. Six real matcher attempts include
one rejected attempt. Report direct-command business rejections, accepted-ID
replays, the matcher cancellation and explicit cancellation separately from
committed trades/fills. No TPS, latency percentile or sustainable capacity is
computed from this finite sample.

Every authority is reopened with the same native configuration. Full main-table
and schema snapshots must match across reopen. Native journal hash replay,
strict matcher correspondence and `reconcile_exchange`'s independent cashflow,
positions and cumulative fee replay must pass. The exact manual customer/fees/
custody balances, signed quantities/costs and journal/posting counts are
independently checked. Expected journal counts are4/6/5 and posting counts8/12/10.
One original actual FILL per authority undergoes the existing decision-audit
**numerical** replay. That replay explicitly does not rerun admission
eligibility, strict-MM permissions, ownership or historical freshness. The
complete audit admission model remains OPEN.

Actual default freshness checks remain at five seconds with one-second future
skew. Quotes are genuine versioned publications at fixed, reviewed points
before operations; there is no failure-driven republish, custom clock, TTL
extension, warmup or automatic retry. Any unexpected first error, stale result,
timeout, output overflow or source drift stops the run and retains original
partial output. Unknown/incomplete receipts cannot pass. Previously confirmed
effects are retained if a later phase fails.

The proposed limits are one CPU, 30 seconds for the target, 64 MiB logical data,
512 KiB shared stdout/stderr including a512-byte failure trailer, a2 MiB source
mini and4 MiB per mandatory JSON report. The caller owns the actual hard-timeout
prefix, original streams, full argv, actual exit/reap and continuous outer
timing. Runtime executable SHA, Python/SQLite versions, flags, affinity and
builtin/extension metadata must match before any database and remain unchanged
afterward. No `/proc` or loaded-library enumeration is authorized. Logical
SQLite sizes are observed between native actions/Python lines; a kernel quota
and blocked-I/O realtime guarantee are not claimed.

All original new databases, sidecars, source copies, action reports and raw
streams remain private and retained. Public delivery may copy synthetic JSON
reports and hashes after review; it does not publish raw database binaries or
borrow archived outputs from another source. No schema/data migration is added.
Rollback follows code-bound authority handoff, preserves confirmed commands,
receipts and journal history, and does not erase this first attempt. Real funds,
performance acceptance and product activation remain unapproved.
