# Python 3.10 fixture successor — Draft / NO-GO

This successor preserves the original frozen source
`dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b` and PR19. Its own branch starts
from exact `5ff974d7cf32715452c4d205efa748e4e4b59f23`. No old source,
code-bound database, original result or failed deadline is rewritten. The final
successor SHA is recorded externally after the final attestation commit.

## Concrete compatibility change

The only test behavior change is in two raw fixture cleanup blocks. After
the actual ledger verifier and strict TEMP-read denial finish, the fixtures
replace `connection.set_authorizer(None)` with an explicit callable returning
`sqlite3.SQLITE_OK`. Python 3.10 does not support removal with `None` in the
way used here, and its subsequent unchanged-state queries fail with
`sqlite3.DatabaseError: not authorized`. Strict verification still executes
before this cleanup. Existing corruption/refusal, same-transaction, snapshot
equality, native managed-read, foreign-path and rollback checks stay in place.

The first-party [Python 3.11 sqlite3 API documentation](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.set_authorizer)
states: “Changed in version 3.11: Added support for disabling the authorizer
using None.” The retained small source metadata/excerpt records the original
HTTP200 fetch at16:52:40.898990 UTC, full-HTML size271807 and SHA256
`d85840c64dce31026a463e64234e4d395bfaa71fadc3475a9d3eec50f9fba61a`.
The complete HTML stays external; this is an API-version source, not an
exchange financial rule. The original5ff author report remains unchanged.

All 62 tracked runtime files remain byte-identical to dbc93e5. There is no
change to the financial kernel, ledger SQL, native credit obligations, account
permissions, product rules, API, database schema or activation policy. The
manifest distinguishes the Git source tree SHA-1, the Git `uta` subtree SHA-1
and the canonical runtime-file-map SHA-256; none is called the other.

## Original evidence stays disqualifying

The original two dbc93e5 Python 3.10 CI jobs each ran 1,801 tests with
11 errors and no failures or skips. Six other jobs succeeded. Only the actual
20 provider artifacts exist: eight unit, six package-validation and six wheel
artifacts. Missing artifacts from skipped steps are not reconstructed.
`docs/dbc93e5-original-ci-integrity.md` preserves exact source/merge identities,
all original job steps and outputs, per-input hashes and private provider ZIP
identities. That source remains NO-GO.

The original independent fresh package exercise and its original positive and
negative archives apply only to dbc93e5. Their package-scope pass, including
installed synthetic V2, is not a full-source pass or a successor package pass.
`docs/release-package-dbc93e5.md` retains those limits and private-material
boundaries. The original dbc blocked six-hour preregistration is retained only
as historical NO-GO planning; it is not a runnable successor plan.

The author retained a 26-target baseline with the same 11 errors, followed by
one 26-target pass each on Python 3.10, 3.12 and 3.13. These targeted fixture
checks, and the separate independent review, do not replace the full final
successor matrix, final CI or fresh package. Original full-local dbc results
are archived separately and cannot qualify this new commit: the natural
16:27:02.425424–16:47:30.559308 matrix has Python 3.12/3.13 each 1,801
passing tests and Python 3.10 1,801 tests/11 errors, with
`source_clean_after=true` and `all_exit_zero=false`. Original worker, summary
and outer-matrix timing boundaries and launcher bytes remain separate.

## Independent review and frozen-source gates

The integration manifest maps each original OWN to its cherry-picked commit
and identifies the independent package and fixture review. The original package
review in `docs/package-dbc93e5-independent-review.md` accepts only exact
dbc package/archive/installed evidence; it runs no product, SQL or financial
work and does not qualify this successor. These reports
sign only their exact reviewed scope. No author report is relabeled as an
independent execution, and no old result is relabeled with a new source SHA.

`docs/ledger-python310-cleanup-independent-review.md` accepts the two fixture
changes only. It preserves the original file-review error caused by an
unavailable local PR merge object, then explicitly narrows that provenance
to retained provider metadata plus actual348 input blobs. It checks the
recorded author runs and API source without executing SQL/product/tests.

After all original evidence and independent reports are integrated, one final
source at `/workspace/uta-credit-v2-py310-candidate` is frozen in place
without another full worktree copy, then pushed as a new Draft PR with base `feat/credit-internal-v2`
(PR19). The original branch and freeze stay unchanged. Root owns a complete
three-runtime local matrix, actual final-source CI8 and one independently built
fresh package with its own review. Future evidence belongs outside that frozen
source or on independent evidence refs. A new anomaly keeps its first raw
output and blocks acceptance.

Any later synthetic smoke and separately preregistered six-hour observation
require their own explicit admission against the same artifact, actual free
space and current independent results. This document authorizes none of them.
It does not supply a successor observation plan or form a source/plan SHA loop.

## Supported behavior, deployment and rollback

The existing internal V2 scope stays fresh-only, default-off, trusted
`synthetic_local`, USD8/BTC8 Cross valuation, BTC BORROW/REPAY, zero new
interest/fee, immutable offline allocation and batch/cache0. Source+PENDING
retain their original producer COMMIT; intent, actual postings, original receipt,
credit decision where required and terminal state retain the financial COMMIT.
Public/CLI new managed borrowing stays501 and trading readiness staysfalse.
Existing standard-authority trading/observer paths still require the full matrix.

No runtime deployment or migration is required for a test-only compatibility
change. Reverting it restores the known Python 3.10 fixture failure. A published
V2 authority stays pinned to its exact retained code/runtime: never erase its
marker, modify historical debt, recycle UNKNOWN allocations or retry under a
new CID to force a result. Recover original CIDs with a qualified compatible
artifact. Forward code/schema upgrade remains unimplemented.

New execution/lending-distress/liquidation adapters, interest/pool changes after
activation, HMAC first-source/revocation barriers, insurance/ADL, real funds,
10k/s capacity, HA/DR and production financial approval remain unenabled or
unaccepted. All public evidence is synthetic. Private original databases,
auth/key/TLS, runtime writer nonce values and signed URLs are excluded; original
archives stay external and preserved. The scoped current/history publication
scan is not a general security audit or production approval.

## Resource observation and immutable source

Root's separate cleanup evidence3959b5c retained exact refs/trees, all16
original archives and1281 other package-file metadata while removing only15
completed clean worktrees and two derived directories. The actual observation
at16:56:35.022556 UTC was16502861824→18671828992 available bytes.
This is an observation of that shared host, not a reservation or a fresh
post-successor-QA/package measurement, and grants no smoke/long admission.
Original raw/archives/private state stay external and unchanged.

The final source is frozen directly at
`/workspace/uta-credit-v2-py310-candidate`; there is no extra full freeze copy.
Root's future commands must use this explicit source path and the final exact
SHA. The preparation manifest records its own preceding Git tree SHA-1 and
exclusions; the final candidate SHA and final full Git tree are recorded in the
external handoff/PR after the last attestation commit. Final QA, package and
observation evidence must not move that source branch.
