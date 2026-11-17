# Historical capacity replay source binding

The8b integration included the correct new measurement footer. The independent
historical JSON checker still compared old environments with the current
benchmark file, so its original136-row fixture group failed once the generator
changed. This repair binds old data to archived original source instead of
reverting the new footer or skipping the hash assertion.

## Retained failure and exact provenance

Evidence commit439565a retains PR44095344867/Python3.12/job134080891989's
original ZIP and all3 members, plus263 original input hashes matching exact
`8b7f544fcbdfd540d43de1d6560022c6ebbd3799`. Its original PR merge identifier
`5cdc9b5abbd6ad86fb031512890d7b685219f8a6` and1472 tests/1 failure/0 errors/
0 skips remain NO_GO. Other CI and local runs are not reclassified here.

All17 original environments have generator hash
`e261712aece4b3826c514a2a029a77327affd362c7a48216029a85a2110dcfd0`.
The exact51601-byte file exists in immutable commit
`5caf874c12b1d053871abe1986784e2a4b883af8`, the helper-patch child of original
parent`e9ec23bf0a54f732b51b91df1bad571dd186dba3`. Original environments still
say that parent and working_tree_dirty=true. The archive commit is an exact
file-source identity, not a fabricated clean original-run commit. The50
recorded UTA source hashes match that immutable source too; this is not full
reconstruction or qualification of the old dirty worktree.

The current51977-byte generator hash remains
`03ae79654c26520f0e95fb85ecfd41cb49f527a0d7cdff92c49df67e4e091746`.
Its actual timing footer is untouched. The original independent checker
hash`34b2625fd0825dfc823d688ae2113dded2c086846578dd127e184a338f50a07d`
and its original manifest are preserved byte-for-byte in the new review
archive and remain available in Git. No previous raw or output was backfilled.

## Replay behavior and verification

The active checker hard-pins the archived source, provenance identity and
original Apache-2.0 license. It extracts only the archived pure gate AST.
Each summary and its separate environment must agree exactly and match the
original generator hash, parent, dirty label and50-file source map. Current
runtime files do not substitute for historical source; their future changes
cannot mislabel old data as current. Current output explicitly distinguishes
the original review base, original generator identity and active replay
checker hash. The counterfactual gate is labeled archived-original rather
than current. These are evidence-report fields, not a trading API change.

The original5 reference cases remain. Five additional contract tests cover
missing pinned source/provenance/license, corrupted source, redirected
provenance, forged current/clean identity and a minimal no-Git/no-UTA bundle
whose current generator intentionally changes and would fail if imported.
Missing/corrupt reference material refuses; a legitimate current-source
change still replays the old17 cases/136 receipts exactly. No database,
financial module, benchmark or service is imported or run by this checker.

Implementation commit24df7d6 was tested once on actual Python3.10/3.12/3.13,
each10 tests, all passed without skips or resource/unraisable warnings.
The CPU3 driver recorded0.258/0.240/0.209 seconds respectively, below the
10-second authorization. Full raw stdout/stderr, commands and before/after
input hashes are retained. These greens verify only this pure reference group;
new full local/CI/package gates still apply to the integrated source.

## Packaging, deployment and rollback

The original generator is stored as `.py.txt`, alongside provenance JSON and
its original license text; existing MANIFEST evidence patterns already carry
all materials in an sdist. The no-Git replay test proves the minimal bundle
works, while a fresh actual sdist/wheel acceptance remains required. Attribution
is the repository's original Apache-2.0 license, hash
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
No MIT license was invented or substituted.

There is no runtime/schema/data migration. Deploy by integrating the review
archive and checker with its entire pinned reference directory, then freezing
and running the complete acceptance gates. Rollback reverts this checker/test
patch in a new commit while preserving all original evidence. It does not
revert the measurement footer, edit original timestamps, modify balances or
relable old CI failures. Historical replay and new performance measurements
must remain separate; no capacity, production or real-funds approval follows.
