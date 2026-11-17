# Exact stable91 integration into the synthetic credit draft

Merge96b9fdb3b6792151299af97b8cd37cb9471f2523 has both original parents:
M3 draft3f5eb0e38ee43bc7ee4a16d3d5ecef6a965380ac and exact stable
91e4ae40b5e9b884c54026406299df5000c9c100. It is a whole merge, not selected
file copying or result relabelling. It required no conflict resolution.

The immutable Git comparison in
`evidence/runs/credit-v2-stable91-merge/compatibility.json` checks every path in
the pre-merge M3 delta, including original actual raw/source identities and
independent observations. All368 paths are byte-equal at the merge. It also
separately checks23 financial/runtime files: original borrowing/repayment math,
native context/SQL gates, audit/FIFO/transition, existing constructors, ledger,
writer fencing, risk and order admission. None changed in this merge. The
unsupported public501 and actual V2 `ready:false` branches remain in place.

The UTA package addition is the stable private-stream codec. As intended, the
credit artifact's complete source-file manifest now has a different identity.
This does not authorize a new build to open or operate an older code-bound V2
authority. Historical decisions continue to require their original exact
source/runtime. Existing private original databases were not opened or changed.
No marker is removed, no old decision/source/CID is reconstructed and no unknown
build is allowed through the native loader. New validations use new fixtures.

One bounded targeted merge regression ran once on CPU3/Python3.12 at
2026-11-17 15:29:37.293763–15:29:38.844062 UTC (1.550s process,
23 tests1.332s), with ResourceWarning treated as an error. All passed:
10 pinned historical-reference cases, five existing-service construction cases,
five managed borrowing501/replay/repayment cases and three actual new-source
code-binding cases. The historical recomputation still explicitly reports its
original a35 source identity,17 raw cases and136 financial receipt rows; it
does not claim a new performance run. Commands/hashes/raw are in `targeted/`.
The previously green21-second process-recovery case was not repeated for this
merge, and old raw was not reattributed to91 or96b.

At this stable91-only checkpoint, root ledger-catalog patch4c260d2 was absent
pending independent acceptance and root's integrated SHA. It was subsequently
integrated with root5a and later F02 MAIN qualification/root7dc; see
`credit-v2-ledger-catalog-integration.md` and `credit-v2-final-candidate.md`.
The fixed final M3 SHA still needs the full supported-Python matrix, CI and a
new package acceptance.
Whole stable91 integration alone does not meet those gates. The draft remains
default-disabled, synthetic-only and overall NO-GO for production or real funds.

Forward upgrade is design-only: an old exact-runtime exporter and independent
read-only audit, a durable intake barrier, full original-CID drain/unknown
resolution, provable old-writer retirement and exclusive static-allocation
handoff are required before a new authority/epoch can own the assets and gross
debt. Current code implements no such upgrade protocol. Binary rollback after
V2 publication must not erase markers/history or silently revive an old writer.
