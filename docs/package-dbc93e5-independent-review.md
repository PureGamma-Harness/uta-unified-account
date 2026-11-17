# dbc93e5 package: independent evidence acceptance only

Independent file-only review accepts the package evidence for exact source
`dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b` and author evidence
`b7f45446341f5433880094bb9592d70ec331b539`. Overall candidate status remains
NO_GO because full current QA/CI and subsequent exact-candidate package gates
are separate. No deployment, smoke, long preflight, live TTL, production,
capacity or HA approval follows. No prior91/460 package PASS was inherited.

The independent audit imported no product code, opened no database and ran no
build, install, CLI, verifier, financial test or collector. It read the frozen
Git blobs, actual archives, installed files and original execution records.
The audit script and its [complete report](../evidence/reviews/package-dbc93e5/review.json)
are retained separately. Frozen source, author reports, raw logs and private
state were not modified.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| Wheel0.5.0a1 | 357465 | `a7c478138c9d1adaa98648efbdca5838aacddbc1d9528d185adf510d008aaa7e` |
| sdist0.5.0a1 | 40342597 | `a7fdf7265407d6fbbad18e1b8ac6477cb4cf988d2cc982571a0065bf96a772d5` |

All5159 tracked files were checked against their exact Git blob identities.
Their SHA256s match the Git archive, build source, sdist and unpacked source.
All62 runtime files match the wheel and fresh installed site-packages; no extra
runtime Python/HTML files are present. The runtime-tree digest is
`ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`.
Static version, entry points, the legacy fixture's pinned bytes and its license
were independently checked. The frozen checkout stayed clean, and build and
unpacked source copies contain no `.git`.

Actual retained results are8 installed CLI tests,8 console commands,3 installed
read-view tests,7 no-Git legacy tests,1 archived-profile test,19 release-verifier
tests and10 historical-source-contract tests, all passing. Execution records
retain full argv, cwd, UTC/monotonic start/end, outer wall and stream hashes.
The installed test processes used the fresh venv's `python -I`, external cwd
and unset PYTHONPATH. The unchanged copied helpers match the frozen source.
All recorded loaded uta module paths are installed:25 CLI,27 views and53 V2.
This means all actually loaded modules, not a claim of actively importing every
available module. All62 installed runtime bytes were independently checked.

Every outer driver command has a real measured wall. Relevant actual walls
were11.463s CLI/console,0.770s views,49.916s runtime-negative collection and
10.020s installed V2, all below their60-second functional limits. The separate
archive-only11-ZIP collection took309.375s within its600-second limit; strict
file checking took21.256s. Nested console and individual primary-negative
records retain their argv/cwd/return codes and streams but do not record
separate per-command walls. No individual durations were invented from the
outer totals.

Both runtime omission controls and all11 tracked historical-ZIP omissions
actually invoked the original frozen primary verifier and returned1. All seven
check keys were present, with only the designated runtime/required-file keys
false. Other report version/helper/runtime bindings matched the positive.
The negative wheel differs by removal of only failure_diagnostics.py; each
negative sdist differs by exactly its designated member. Every remaining
member's content, stable metadata, order and wheel ZIP comment are identical.
Physical ZIP offsets necessarily change after removal and are excluded from
stable-member metadata. The other positive artifact stayed byte-identical.
No negative archive was installed.

The11 original historical ZIPs remain byte-exact members of the source/sdist.
Their summary/worker/log results still report their original failures, original
code_commit and log hashes. Their before/after source maps were independently
checked against the explicit historical reference commits. These historical
results are preserved evidence, not current CI qualification. All127 public
safe copies are byte-identical to their original external files.

The fresh installed-wheel V2 run actually prepared native capability, acquired
its real fixture token, committed a four-leg BTC0.4 borrow and four-leg BTC0.1
partial repayment, leaving debt0.3 and exact integer balances. Original CID
query/replay returned the original receipt without another financial effect.
A separate unbound read-only reopen completed the real factory/full credit
validation and ledger replay of4 events with1 nonzero liability, query_only
and unchanged financial state. New public borrowing remained501 and READY
remained false. Original BEGIN/END stdout matches the retained V2 JSON. Fixture
sources came only from the byte-checked unpacked sdist; uta stayed installed.
The fixture uses a static synthetic financial clock. This is not live lease/TTL
freshness or production availability evidence.

The external root `/tmp/uta-release-dbc93e5-oor3dlj4` retains both positive
artifacts, Git archive,13 negative artifacts, every raw output, build/unpacked
copies, venv and private DB. This review deletes nothing. A later candidate
with different tests/source needs its own exact bindings and required gates;
this dbc93e5 package result cannot be relabelled as that candidate's result.
