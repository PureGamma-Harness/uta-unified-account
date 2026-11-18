# Fresh-SQLite account-inventory correction: independent closure

**CODE_ONLY CLOSED** for control source
`e707fc55e83f53d79aa27610ea8f7b6386f6c713`, tree
`255729d48af95f1dc2d425cc90e01881a140721b`, and its exact source manifest
SHA-256 `2bfda9eed7530fdfd0f462648e86cbcb3bf546b1fc2c3971894338ce81d51b4c`.
This closes the sole preparation finding in independent commit `6f644c27`.
It grants no execution permission and records no SQL result. Target imports,
compilation, tests, SQL, process probes and network were not executed.

At `sqlite_case_once.py:227`, `expected_accounts` now expands the complete
prior account map and replaces only A's row with a copied row whose version
increases by one. The following whole-map equality checks every key and row,
so added, removed or otherwise changed accounts fail. Replacing exactly these
two statements with the old assertion mechanically reproduces the entire
previous case AST. The driver is byte-identical to the reviewed predecessor;
all native financial files remain byte-identical to `402c784`. No business,
fee, clock, cancellation or profile-observer behavior changed.

The new plan SHA-256 is
`c4e4604c6bbab13c5fb3799de8fc84e42d36b86b88c9ebf68576793e6237cc0c`.
Its financial cases, counts, budgets and command template equal the previous
plan after removing only the added preparation-history description. The new
63-file mini is 1,326,999 bytes; the declared 70 physical files total
1,401,918 bytes. Their canonical regular paths, complete recorded stat maps,
lengths, SHA-256 values and Git blobs match. The manifest metadata is frozen at
`b5739962`; final materialization OWN is `0d0a0970`, tree
`40fe40725509cde975c0b7ef5fc20219c4f450ef`. The materialization record SHA-256
is `e0f07f36cf892494cd11cdff420b1760dbbc50c11a9307bdc53a5e5769c6b1c9`.

The reviewed host template retains hard `timeout --signal=KILL 30s`, CPU1,
the pinned Python with `-I -S -B`, the original `sqlite_once.py`, exact
`--source-commit e707fc55e83f53d79aa27610ea8f7b6386f6c713`, exact
`--approved-manifest-sha256 2bfda9eed7530fdfd0f462648e86cbcb3bf546b1fc2c3971894338ce81d51b4c`,
and a separately authorized new private direct child of `/workspace`. The
metadata/OWN commits are not substitutes for that control-source argument.
Caller-side immutable-driver binding, O_EXCL capture, actual argv, exit/reap,
complete raw and timing remain required. No host invocation occurred here.

The inherited limited static review covers the three real-API synthetic
authorities, exact native matcher/savepoint/cancel flow, independently derived
cash/fee/position expectations, bounded read-only profile and reviewed audit
hook. Planned totals remain 5 authority-qualified matches, 10 paired fills,
6 matcher attempts, 3 direct-command rejections, 2 known-ID replays and one
automatic/one explicit cancel. They are not observations. The 30-second,
CPU1, 64-MiB logical-data and 512-KiB shared-raw budgets are unchanged; no kernel
quota, complete sandbox or performance assurance is claimed.

The prior `fafd595` plan385 and manifesta455 are retained as byte-exact
`-fafd595-NOT_RUN.json` files, with the static finding and zero attempts. They
are not RED and are not retrospectively closed by this new source. Independent
`6f644c27`, first PURE and its `3987a0bd` review, plan92fc, original inputs,
and the `23f439a` post-terminal materialization event remain unchanged.
Full audit admission-eligibility modelling, broader compatibility, performance
and production qualifications remain OPEN or false. Root must separately
authorize the first actual SQL run on this exact source and manifest.
