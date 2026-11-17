# Independent release contract review: e9ec23b

Reviewed source: `e9ec23bf0a54f732b51b91df1bad571dd186dba3` on an isolated
worktree. This is an independent static review of release declarations,
documented product boundaries, the API publication fixture correction and
deployment/rollback contracts. No service, SQL operation, unit suite, load,
observer sample or soak job was executed or changed. It does not establish a
security scan, financial sign-off or production acceptance.

Verdict: **no implementation blocker identified in the reviewed version and
fixture changes; final release freeze remains blocked by documentation updates
and exact-source qualification. Production remains NO_GO.** This review is not
an independent revalidation of all batch/cache implementation paths.

## Runtime and operation contracts

`DurableProcessRouter.__init__` in `uta/durable_process.py:927` defaults
`financial_batch_size=0` and `normal_cache_size=0`. It accepts batch zero or
3..8, rejects bool/noninteger cache capacity and limits cache capacity to
0..65536. A nonzero batch choice without the persisted capability fails with
`409 batch_capability_required`. The CLI preserves both zero defaults and the
same supported domains. Initialization's `durable_batches` defaults to false;
its explicit fresh-layout format capability is irreversible.

The managed client route and trusted credit service have distinct rejection
contracts. `uta/durable_gateway.py` returns `501
unsupported_durable_operation` for an unsupported customer operation;
`CreditService._borrow` in `uta/credit.py:272` first checks the canonical
original credit receipt, then returns `501 unsupported_credit_operation` for a
new borrow on a persisted managed authority. The new joined helper cannot
authorize borrowing merely because it shares a financial transaction. Its
caller must roll back its savepoint or whole transaction on late failure.
The milestone and managed-credit boundary document describe these limits
accurately and do not claim an operation-specific native SQL old-binary gate.

The existing durable milestone's product matrix remains a valid narrower
reference: synthetic USD Cross linear limit orders, cumulative reduce-only,
cancel and existing same-currency debt repayment; unsupported managed market,
conditional, amend, multileg, new borrowing, spot, account-mode change and
cross-shard transfer/matching operations stay disabled. The reference/standalone
spot and credit paths do not inherit managed ingress or operational approval.
PM, Isolated, real USDT/USDC, dated, inverse and options production remain
disabled. The next milestone should link this matrix explicitly so that a
reviewer need not infer that its optional batch/cache flags add no products.

The rollback directions agree across the implementation and cache documents:
halt entry, preserve and query original CIDs, drain/reconcile, close the old
owner, restart capable fixed code with numeric batch/cache flags zero. Zero
batch size does not remove persisted capability or skip pending-manifest
recovery. Old incapable binaries, deleting manifests, resetting generation,
restoring away confirmed effects and bypassing the borrowing refusal are not
valid rollback procedures. Cache state is disposable and requires no schema
or monetary migration.

## API phase correction

`82688a62cff7cbde897f0a9a61f1447f0ad7d928` changes no `uta/` file. Static
comparison of the complete changed test confirms that the original `.25`
publication timeout, two-second snapshot age limit, real owner lease,
original timestamp and subsequent natural stale/recovery assertions remain.

Before stamping the first quote the fixture waits for the actual local READY
owner. After partial publication it queries that publication's original CID
within one second and requires `SUCCEEDED`; it then asserts exact original
version, UTC timestamp, payload digest, snapshot ID and stored bytes. Shard 1
must remain PENDING and global control HALTED/publishing. No missing, stale,
retimestamped or replacement publication can satisfy the fresh assertion.

The new dual-owner hold case explicitly checks the missing/PENDING phase,
releases only shard 0, retries the same publication IDs, then completes the
same snapshot. This is a phase precondition correction with an additional
negative control, not a relaxation of production freshness or acceptance.
The original CI artifact and its unproven unique scheduling cause remain
recorded. This static verdict does not claim Python 3.11 reexecution or full
CI success; those require the new frozen-source run.

## Version and package identity

The declarations consistently identify `0.5.0a1`; historical `763202d`
consistently remains `0.4.0a1`. The archive verifier reads both tracked
declarations from the requested exact Git commit, rejects HEAD/source drift
and nonignored untracked source, parses the initializer without executing it,
and requires a single static literal equal to controlled `[project].version`.
The deliberately limited TOML reader is documented and fails closed on
unsupported version declaration formats. It is not a general TOML validator.

Wheel acceptance requires exactly one distribution METADATA member and
exactly one case-insensitive Version header equal to the frozen declaration.
Duplicate archive member, unexpected runtime, exact runtime bytes, all tracked
sdist paths, legacy fixture and entry-point checks remain. Installed
acceptance compares both distribution metadata and `uta.__version__` to the
artifact manifest instead of the old hardcoded version. `--identity-only`
still records zero functional tests and must not substitute for actual
installed financial acceptance.

The focused fixture evidence supports the tool contract, not a built 0.5
release. A real build/install must use the final reviewed source, fresh
isolated installation, exact archive manifest and real omitted-file negative
controls. CI's ordinary wheel smoke also does not replace this broader
wheel/sdist/installed acceptance.

## Freeze blockers and required evidence

1. `docs/milestone-batch-credit.md:47` still describes cache integration as a
   future merge. Update the current milestone before freeze to include merged
   default-off NORMAL cache, the actual batch/cache combination evidence,
   numeric boundaries, 0.5 declaration, fixture-only phase correction and
   initial failed CI/full-preflight records. Preserve their original results.
   Include the supported/rejected product matrix and both numeric flags'
   rollback behavior. Existing complete evidence references stay historical.
2. `evidence/rules.csv` has batch and borrowing rules but no explicit NORMAL
   cache rule. Add a trace entry covering default zero, capacity bounds,
   current full read-only proof/freshness/native guard assumptions, failed or
   unknown proof-COMMIT cache exclusion, same-source equivalence tests and
   disposable-cache rollback. Its evidence must not imply a performance gain.
3. SOAK-002's last field currently says no qualified six-hour run has started.
   It is an earlier recorded state. Append a clearly dated execution-status
   entry or link the actual job evidence rather than rewriting old results.
   The live `763202d` producer/observer identity, original duration and any
   retained UNKNOWN/coverage NO_GO stay distinct from financial completion
   and from the new 0.5 source. That job cannot qualify different 0.5 code.
4. Freeze only after pending benchmark helper/configuration changes and the
   above documentation are incorporated and the checkout is clean. Run the
   full exact-source local runtime matrix, independent push/PR four-version
   CI and fresh actual package acceptance. Keep old failed artifacts and
   actual PR merge SHA separately from the head/source manifest identity.
   The prior single-runtime 1219-test preflight's known failure is not a
   completed new full release gate.
5. Capacity comparison requires selectable actual batch/cache settings,
   persisted-capability equality, unchanged policy, actual selected/executed
   counts and all-original-CID failure gates. A manifest is not a financial
   COMMIT or admission. No 10k/s, six-hour, 24-hour, replicated/AZ recovery or
   real-funds approval follows from the reviewed code or this document.

## Review evidence and limits

[Static checks and source hashes](../evidence/runs/release-gate-review-e9ec23b/static-checks.json)
bind the inspected files to the reviewed commit. The checks only parse Python
ASTs, validate the CSV's 15-column structure, call the side-effect-free version
declaration parser on the two frozen Git blob pairs and verify the API patch
has an empty `uta/` diff. They execute **zero runtime tests** and perform no
database or live-job reads. The read-only review document and this evidence
are the only files added by this review.

## Addendum: documentation correction 1edaec0

After the initial source review, integration commit
`1edaec0f3519473eaf8de45cad65adabb19b8f2e` was inspected by `git show` without
moving this review worktree or changing its runtime. It modifies only the
milestone and appends three CSV rows. The cache integration, actual combination
cases, numeric zero defaults, declaration-only 0.5 status, original 1219-test
failure and fixture correction are now reflected. NORMAL-CACHE-001 and
BATCH-CACHE-001 expressly preserve proof/fencing, actual execution prefixes,
and unqualified throughput. SOAK-003 dates actual startup and existing coverage
NO_GO, preserves SOAK-002 and makes no completed-duration or replay overclaim.
These changes **close documentation findings 1–3** above for this scoped review.
Exact-source full/CI/package and subsequent capacity gates remain open.

The product table keeps managed Cross narrower than reference services and
does not enable Isolated/PM or later products. One wording clarification is
recommended: explicitly say managed spot orders also return the unsupported
HTTP operation contract, because the row titled new borrowing/spot currently
states only the new-borrow 501. The linked durable API already states this
restriction unambiguously. Describing cache reuse as repeated NORMAL
supervision results would also be more precise than merely diagnostic results.
Neither recommendation authorizes a product or changes a runtime gate.

Commit `ceb15c7` was then inspected read-only. It replaces diagnostic-result
wording with repeated NORMAL supervision results and explicitly states both
unsupported v2 new-borrow/spot operations' `501
unsupported_durable_operation`, separately from trusted credit's `501
unsupported_credit_operation`. Both wording recommendations are closed.
The final scoped verdict therefore has **no outstanding documentation or
reviewed implementation blocker**. Full exact-source qualification, capacity,
long-duration, replicated recovery and financial/production approval remain
independent open gates.
