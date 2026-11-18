# Independent fresh-SQLite preparation review

Source `fafd5959451b283e93a6124c318982e052256b8c` is **CODE NOT CLOSED / NOT_RUN**
because of one bounded rollback-assertion finding. No target import, compile,
test, SQL or probe was performed. This is a preparation finding, not a runtime
RED or evidence of a financial mutation.

At `sqlite_case_once.py:225-228`, the rollback check excludes `uta_accounts`
from the general exact-table comparison, then checks only A's version increment
and unchanged B. It does not compare the complete account-ID sets. An added
empty account could escape this assertion and the cash/position oracle; the
independent reconciliation does not impose the expected account inventory.
That falls short of the stated exact allowlist of one A cancellation version
change and unchanged remaining accounts. It does not show that the fixed
Matcher actually creates an extra account.

The minimal correction is to compare the complete account map against the
complete prior map, changing only A's version by one. Requiring equal key sets
before the existing A/B assertions is sufficient for this fixture. This needs a
new frozen control source and rebound case/manifest/materialization pins before
an execution authorization; the current source remains zero attempts.

The remaining limited static review found no additional blocker. The 61 native
UTA files, 1,283,677 bytes, equal the previously reviewed `402c784` source. The
two controls make a 63-file mini of 1,326,982 bytes. All 67 declared physical
files, 1,367,332 bytes, match canonical regular-file identity, stat metadata,
length, SHA-256 and Git blobs. The approved manifest is SHA-256
`a455f2ca642306368daa198d264917c3622b60cfc49586c5ab45e0aa1e45d729`;
plan SHA-256 is
`385c64dad0dbca85e754dbcf394210f8a10aa33accaf5a315da46edc07acb411`.

The case uses original `ExchangeService`, `Database` and `Matcher` without
method, clock, argument or connection replacement. The actual matcher source
settles buyer first, then seller inside a savepoint, rolls both back on a
business failure, and applies its existing cancellation only to the rejected
order. The read-only profile observes exact native code objects, scalar guard
values and B's real return before A's call, retains at most 32 records and is
removed in `finally`. The audit hook permits this profile API and confines
SQLite targets and writes to the new synthetic scope. Unmanaged initialization
does not enter the managed boot-ID path. No auth, funding or cancellation policy
was relaxed.

The three manual expectations are internally consistent. In the first case,
ETH trading leaves A cash 11.04000009; the mark loss 0.00000010 and proposed BTC
fee 0.04 leave equity 10.99999999, equal to IM/MM. The planned direct rejection,
buyer-first/seller-second rollback and distinct fresh admission rejection
exercise that boundary. The lower-MM case preserves IM availability zero,
then RO closure leaves A9.96, B999.92 and fees0.16. The USD2 partial case charges
the one seller order [0.01,0] and two distinct buyer orders [0.01,0.01], leaving
A0.10, B9.98 and fees0.03. The asserted 5 matches, 10 fills, 6 matcher attempts,
3 direct-command rejections, 2 known-ID replays and one automatic/one explicit
cancel are planned outcomes, not observed results.

The reused raw writer, SQLite builtin/extension descriptor, scope audit,
report writer and trace callbacks have the same AST as the reviewed `3b0c49a`
driver pattern. The new source mini and its origin checks are pinned; actual
runtime identity, flags and CPU1 are checked before any business database and
again afterward. The caller must separately bind the loaded driver and preserve
O_EXCL raw, actual argv, hard 30-second prefix, exit/reap and timing. The 64-MiB
data ceiling is logical observation, not a kernel quota or blocked-I/O bound.
The shared 512-KiB raw limit and reserved failure trailer are independent of
that logical data limit. No timeout, overflow or hook path was executed here.

Three actual FILL numerical replays, independent cashflow reconciliation and
literal manual balances are in the proposed scope. They do not prove a complete
audit admission-eligibility model, legacy mode, position-limit/freshness boundary
acceptance, performance, HA or production readiness. Those broader gates remain
OPEN or false. The first PURE evidence, plan92fc, original inputs and old 7c8
NOT_RUN finding are byte-protected. The explicit `23f439a` post-terminal
rematerialization record is retained; historical and current inode/timestamp
identities are not equated. This review changes only its own safe files.
