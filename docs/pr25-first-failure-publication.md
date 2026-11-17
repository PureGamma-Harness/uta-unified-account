# Original PR25 failure evidence delivery

This documentation-only delivery preserves the first push failure at source
6010e920a168b35fccfc9ef9ee34e030b28b11d9, its independently verified artifacts,
and the bounded SQLite timing interpretation. No runtime, tests, timeouts,
workflow or financial permission changes occur. See
`ci-6010e92-first-failure.md`, `ci-6010e92-sqlite-protocol-timing-review.md` and
the separate independent document review.

The first push311 failure remains a release blocker. The green PR-run has the
same Git tree and does not replace it. The diagnostic does not establish a
root cause or a measured duration for its native writer probe. Current SQLite
documentation is evidence for hypotheses, not verification of the exact
3.46.1 library source.

The publication commit uses `[skip ci]` because its only changes are retained
evidence and documentation; it is not a runtime qualification or a CI retry.
The source/merge identities, first results and 353-input byte bindings stay
unchanged. The bounded publication-pattern check is recorded separately and
is not a general security audit. Private original binary archives and official
document bodies remain external; no download credential is published.

Rollback may remove documentation links but must retain original failure
records and external evidence. Production, real-funds, sustained capacity,
multi-node durability and long-run acceptance remain closed independently.
