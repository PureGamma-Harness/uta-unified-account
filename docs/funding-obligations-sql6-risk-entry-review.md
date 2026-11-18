# Independent risk review: funding obligations SQL6 entry

The revised entry has **limited CODE closure** at metadata commit
`9171e8e5e8d16b99a8a46f2f6ec1563754f55811`, source origin
`3b459f797d2fd526d81f9cefb97002d7e5c91d60`. No additional confirmed blocker
remains in this bounded synthetic SQL6 proposal after the F1 control-path fix.
This is not an execution instruction or a production sign-off. All six methods,
nine databases and two competitor threads remain **NOT_RUN**.

The review used source reads, Git/physical byte comparison, JSON inspection and
independent hand arithmetic. It did not import or compile target modules, open
SQLite, run tests, start target threads/workers/processes, inspect processes,
signal anything, benchmark or trigger CI. No financial source was repaired by
this reviewer.

## Immutable inputs and original evidence

All 69 new plan inputs matched physical SHA-256 and committed Git objects,
totaling1,490,461 bytes. Plan SHA-256 is
`02f57cfb7d55498c436ed61243f7180d1ba51995209e3b5c09b8d49b28761ea1`;
caller-plan SHA-256 is
`155950087c7d9a6785b9b76d55df43d8b5b959427088ec4347a6898a3f34d6c4`.

The new entry is44,786 bytes / SHA-256
`80bc312ad254fdb1f8e3d38068050fece9fb26eee87a076c7f365be2127cf9a4`;
the separately pinned caller is23,159 bytes / SHA-256
`934216efb87926a5860d8830566faacb15f9dd231a1ffc664ecb57e13adf1f4e`.
The independent oracle is18,772 bytes / SHA-256
`e9b1e44c9ea46d28a8d432384c873f028e3ac8952a944b439f3126fe92594825`.
The runtime binary/flags/CPU values are fixed future on-entry checks, not a new
runtime execution result from this review.

All64 UTA files, the original test source, the90e manual plan and runtime
manifest are byte unchanged against financial source
`90e81daa7b7cb398664c1dadb3a0d943e45321d6`. The original901/90e materials are
not replaced. The original SQL6 source27c8b466 / metadataeb778b91 and its three
metadata files are retained separately under `sql6-27c8-NOT_RUN`; their hashes
were checked against the old Git blobs. There was no target failure, retry or
test result at either revision. F1 was a source-review finding.

FUND-OBL-001/002 keep the limited financial CODE conclusions in review
`f665e4e20975a04cd57d476694a68a77a389887b`. FUND-OBL-003 remains withdrawn:
the public `_validate_market_command` always requires the USD quote. This
entry does not bypass that guard or change the financial source to address
the rejected candidate.

## F1: database byte reads require proven native closure

The original27c8 entry computed final DB hashes unconditionally, even when
its close observer could not prove all SQLite handles closed. Setting PASS
false did not prevent the read/open/close. The storage implementation explains
that closing an ordinary FD on a SQLite inode can release this process's
other fcntl locks. The source comment saying hashing occurs after closure
was therefore insufficient on the UNKNOWN/failure path.

The3b459 revision places the DB-byte read behind a real predicate requiring
successful closure observations, complete connection/path accounting, intact
profiles, no sticky observer/forbidden error and quiescent declared threads.
When that predicate is false, only stat facts are retained, the DB bytes are
not opened or hashed, and qualification fails. The caller checks the same
permission/error evidence before opening DB bytes for hash verification.
Native-close observer exceptions are sticky, including when Python disables
a failing profile. There is no cleanup close that restores PASS.

F1 is **closed at CODE level only**. No resource failure or native lock fault
has been injected or executed. The revision changes the entry/caller/contract
and source metadata, while preserving financial code, fixture, independent
oracle, manual values and resource limits.

## Financial workload and oracle review

The entry loads the whole retained fixture and selects the six original
methods in a fixed fail-fast order. Its scenario wrapper retains original
objects and enforces the nine labels; it does not add financial setup,
replace a financial method, change a publisher, alter test assertions or
repair stored market history. The existing CASE_ROOT mechanism retains
normal, missing, current-data, capital, competition, changed-positions,
new-empty, old-empty and review as separate fresh authorities.

Independent fixture accounting agrees with the frozen manual values:

| Namespace | Journals | Qualified matches | Fills | Final obligations |
| --- | ---: | ---: | ---: | --- |
| normal | 6 | 1 | 2 | 1 APPLIED |
| missing | 4 | 1 | 2 | 1 REVIEW_REQUIRED |
| current-data | 6 | 1 | 2 | 1 APPLIED |
| capital | 11 | 2 | 4 | 1 APPLIED, 1 WAITING_CAPITAL |
| competition | 6 | 1 | 2 | 1 APPLIED |
| changed-positions | 8 | 2 | 4 | 1 APPLIED |
| new-empty | 0 | 0 | 0 | none |
| old-empty | 0 | 0 | 0 | none |
| review | 5 | 1 | 2 | 1 REVIEW_REQUIRED |

Totals46 journals include the deliberate orphan. Nine matches/eighteen fills
are qualified by namespace, not globally unique business IDs. Fees.72,
custody-15001, eight obligations/five APPLIED/three outstanding, and seven
immutable cuts are planned hand oracles, not observed results. The caller
does not manufacture a matching schema in either empty namespace. The review
namespace must remain unhealthy and the original funding verifier must reject
its deliberate orphan; a readable REVIEW is not a healthy financial authority.

The read-only oracle independently replays integer double-entry postings and
materialized balances, recomputes ledger and funding command/event hashes,
checks current quantity/cost, joins each real matching receipt to both original
orders/fills/fee-PnL journals, recomputes toward-zero frozen cash legs with
Fraction, and checks receipt/cut/current-risk references. It does not call UTA
financial arithmetic or hashing helpers. The original component funding
verifiers run separately and are labeled separately. The limited independent
oracle is not a replacement adversarial validator for every optional schema
or a complete independent supervisory eligibility replay.

In particular, the original cut and current market are distinguished. At
current-data mark101, cash999.95/999.97 becomes risk equity1000.95/998.97 with
MM5.05 each. Genuine post-cut closing trades at101 leave1000.91/998.91;
frozen-1/+1 then makes both999.91 with flat positions, IM/MM0 and a legitimate
USD-only current market. The historical BTC cut is not treated as a current
position. The missing-current-mark helper remains a read-only negative control;
it does not prove persistent partial-market corruption/recovery.

Capital q.4/-1/.6 at mark1/rate.015 gives exact-.006/+.015/-.009 and actual
0/+.01/0. The .01 variance comes from the fixed treasury's confirmed1 deposit
and real .01 transfer, leaving treasury.99 and customers999.93/999.97/999.97.
The next period's reused proof is rejected without consuming more money.
No loan principal or interest is created by these funding operations.

The independent final-state risk formula uses actual ledger/position/current
market rows, with explicit rejection outside the registered USD1, fixed
linear policy, zero liabilities and no live orders. It does not take receipt
risk output as its input. Capital risk equity960.33/1098.97/940.57 and
MM.02/.05/.03, and the other registered cases, remain healthy. Runtime
evidence of crossing MM, negative cash, bankruptcy, loan-only distress or
supervisor eligibility is still OPEN. `risk_eligibility_replayed` remains false.

## Native resources, containment and acceptance limits

Native SQLite connect and connect/handle audit events bind the actual native
objects and nine allowed URI families. Strong references prevent identity
reuse. The profile observes only successful native Connection.close c_return
events in the closing thread; c_exception is not success. It records no frame
locals or financial/nonce values and does not probe or close foreign-thread
connections. Missing closure, callback error or profile change fails
qualification. The initial profiles must be None; finally restoration has its
own record, which the outer/caller must validate.

Exactly two original ThreadPoolExecutor worker starts are permitted in the
competition method, with the original Barrier/future timeouts retained. No
other test's thread, service worker, network or target subprocess is allowed.
The suite must report six exact successful IDs with no failure/error/skip,
both declared threads quiescent, all handles already closed, and nine genuine
read-only reopens with unchanged schema. A late close/reap/EOF or cleanup does
not restore successful qualification.

The proposal fixes CPU1, native target timeout45s, target/drain classification
50s, caller global75s plus failure cleanup wait2s/drain.2s, inner raw256KiB,
caller raw1024 bytes, per-file4MiB, observed logical DB64MiB/45 files and
control8MiB. The disk aggregate is a boundary observation, not a hard continuous
aggregate quota. The held pidfd owns only the newly born gated outer, after
rejecting the protected historical numeric IDs; no old process or authority is
looked up or signaled. Normal PASS requires actual natural exit/reap and EOF.
Failure containment still relies on the new native target timeout; no executed
process-tree crash/cleanup guarantee follows from this CODE review. The root
must independently observe the caller's actual exit and EOF.

Pending funding in order/withdrawal/transfer reservations, managed and
old-binary exclusion, a due scheduler, wallclock/clock faults, persistent
partial-store recovery, commit/crash faults, HA, custody/operations and capacity
remain OPEN. This work supplies no production, throughput or real-funds
approval. Separate immutable literal invocation approval and runtime/RAW
acceptance are still required.

Deploy only into the newly declared private synthetic namespaces after that
separate gate. Keep DBs, full capsule/raw output, claims/nonces and concrete
birth bindings private; future public delivery must be a separately reviewed
finite SAFE projection. Rollback stops explicit calls and preserves every
task, unpaid cut, command, receipt, journal and first failure. Never delete
capability markers or hand the new database to the old prototype.
