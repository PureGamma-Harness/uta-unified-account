# First actual SQLite result: independent scoped evidence PASS

Owner seal: `3da0ee847042e995dae57778a8f7f3a7245cfeb5`; executed source: `3b0c49a6df6773ea7cdb208945541480ea091ea8`.

This is independent inspection of captured files and exported SQL rows. The reviewer imported no UTA module, connected to no SQLite database, reran no target, queried no PID and made no network/capability probe. The eight database files were read only as byte streams to bind the captured inventory, with O_NOFOLLOW/O_NOATIME and unchanged file metadata.

## Original and source binding

All19 newly committed public files match their Git blobs. The17 sealed files match their exact lengths/SHA256. All11 public report copies are byte-identical to this run's private originals:4,906,804 bytes. All82 listed private inventory entries, including the retained database bytes, match. All63 original/snapshot source hashes match the approved manifest and the original captured before/after maps; all18 recorded UTA module origins refer to that mini-source. This is source/output binding, not independent observation of past kernel execution.

The complete76,270-byte stdout matches SHA256 `6bf03110cad36fc4607c03a3ed96dc742813a48cd084ae3bcfd89463344a025b`; stderr is empty. Its472 finite, duplicate-key-free JSON records contain BEGIN,470 checkpoints and END. The recorded actual exit is integer0 and the scope records one invocation, no retry. Original elapsed fields remain distinct: result10.072730762010906s, END10.144206064011087s. Outer lifecycle monotonic time was not captured and remains null. These are not throughput/E2E latency measurements.

The recorded runtime is Python3.12.14/SQLite3.53.1, CPU[0], builtin _sqlite3 with null extension path/SHA, actual executable digestfa674435…d15d5ea7. Loaded libraries remain null/NOT_OBSERVED; no current maps were inspected. Source and metadata compatibility do not constitute complete runtime attestation.

## Independent captured-financial checks

A separate standard-library reader reconstructs ledger event fingerprints and the complete hash chain, checks each event's per-asset double-entry sum, and recomputes ledger balance units. From the captured chronological fill events it independently reconstructs signed position cost, realized PnL, cumulative fee ceilings and each fill's journal postings. It also checks actual trade identity, both matching fill sides, cumulative order quantity/notional/charged fees and all retained positions.

| Existing case | scan matches/fills | snapshot matches/fills | Independent check |
| --- | --- | --- | --- |
| FIFO/STP/partial | 2/4 | 2/4 | Correct buyers, newer self-order cancelled, each account9999.96, residual reserve20.08 |
| RO cross-cancel | 3/6 | 3/6 | Later RO cancelled/unfilled, victim quantity1/cost100/cash9996.8012 |
| Second-leg frozen | 0/0 | 0/0 | Real account_frozen receipt for seller; buyer/account and ledger unchanged, buyer order open, seller cancelled |
| No liquidity/halt/resume | 1/2 | 1/2 | Final cash9999.9208 each, actual paired price99 fills retained |

The seller-state mutation remains a declared synthetic status fault, not full liquidation acceptance. Each mode totals six matches/twelve fills. IDs deliberately repeat across the two separate authorities; they cannot be summed into global unique throughput.

The reviewer independently reconstructs each exported economic comparison projection from full raw tables, retains complete ledger hashes and financial/business fields, and applies only the declared timestamp/market-reference exceptions. Reopen captures are equal and the two modes' final financial/risk projections are exact. The captured strict matching and independent cashflow replay receipts agree with these counts and report no unpaired fills. Six nonempty authorities each retain one actual FILL valuation-replay receipt with matches=true/differences empty. The reviewer did not invoke those production replay methods again.

## Separate reviewer-reference correction

The first execution of the reviewer's optional JSON decision-value checker failed because its own initial reference incorrectly waived adverse execution loss for reduce-only orders. That reader source and full error/exit remain in commit69b4958 and first-reader-failure.json; the target and its first receipts were not rerun or modified.

The pre-existing system specification is explicit in source3b0's docs/kernel-validation.md:11–15 and docs/reserve-kernel.md:31–38: reduce-only waives IM; adverse loss remains max(0,r×(limit−mark)); unpaid cumulative fee remains separate. For r=-1, mark100, limit99 and fee0.0004 at8 decimals, loss1 plus fee0.0396 gives reserve1.0396. This is a documented signed-quantity rule, not a fitted tolerance.

Only that reference line changed. The corrected reader passes. Its supplementary five-field valuation checks over already captured decision states use independent rational arithmetic and the fixed100 mark; they are separate from the necessary eight-authority evidence checks and from the six producer-executed replay samples. They do not establish that every historical decision was executed through replay or that all production risk fields/models are validated.

## Acceptance boundary

**SCOPED_ACTUAL_SQLITE_EVIDENCE_PASS**: single-process synthetic legacy-USD matching functional evidence, bounded by the exact source/cases above. No remaining discrepancy was found in that scope.

The observed tree length8,602,820 bytes is below the64MiB monitoring budget, but neither unsampled C-write peaks nor a kernel quota/hard I/O deadline are proved. Python end-state thread count1 is not kernel thread enumeration. No managed fencing, process concurrency, HA, custody, actual USDT/USDC, configured product models, sustained capacity,10k/s, default snapshot activation, real funds or production approval follows. Prior PURE037 and d517 NOT_RUN history remain unchanged.
