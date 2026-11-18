# Independent first E707 SQLite RAW review

**RAW binding PASS and limited native SQLite functional PASS** for control
`e707fc55e83f53d79aa27610ea8f7b6386f6c713`, manifest SHA-256
`2bfda9eed7530fdfd0f462648e86cbcb3bf546b1fc2c3971894338ce81d51b4c` and
plan `c4e4604c6bbab13c5fb3799de8fc84e42d36b86b88c9ebf68576793e6237cc0c`.
Author evidence is `356fb399f3638df24fb30ee0dd36c81063a4256f`, tree
`9cd07b24ab9577877fc85ea6061353146d0aa1f0`. This conclusion follows actual
terminal originals. The reviewer did not import/compile targets, run SQL,
reopen databases, rerun cases, probe processes or start a child agent.

All80 originals/4,939,245 bytes equal the private seal and ZIP members;
all80 CRC checks pass. The private archive is1,087,363 bytes, SHA-256
`08736915ac57a5f225b61a2aa8a63946e91740832284b513f6ee047bc15d4d54`.
Three database files were hashed as bytes, never opened with SQL. Private
roots are0700, source-copy files0400 and other originals0600. The10 SAFE
outputs/112,125 bytes match export manifest SHA-256
`0ac85c415a1eb1221b6a7d9420553b14c455133ea09fb7d2fa6fe59f53325783`.
All three SAFE authority objects exactly equal independently reconstructed
explicit field projections. Schema/table/outcome hashes were recomputed from
sorted-key compact JSON, separately from ledger hashes. Summary facts, raw
event key sets and80-entry byte inventory also match their originals.

The actual limited outcomes are:

- Three authorities contain5 unique authority-qualified matches and10 paired
  fills, with zero unpaired fills. Five Matcher API calls made6 pair attempts,
  including one MM rejection. Three direct business rejections, two accepted-ID
  replays, one automatic cancel and one explicit cancel remain separate counts.
- The profile observes B's provisional FILLED return before A's seller call
  reaches actual equity=MM=10.99999999, availability0. Rollback leaves exactly
  the allowed accounts/orders/events cancellation changes. The complete account
  map equals the prior map with only A.version+1; other rows and schema match.
  B's provisional return is not a committed fill. Direct rejects and known-ID
  replays each leave their complete captured business state unchanged.
- The lower-MM case accepts equity10/IM10/MM5/availability0 and closes both
  sides through the original RO path. All three reopen snapshots match. Native
  ledger/strict matching and independent cashflow/position replay pass. Literal
  cash, custody, fee and signed position/cost expectations match; journal counts
  are4/6/5 and postings8/12/10.
- USD2 seller fees are[.01,0], while distinct buyer orders pay[.01,.01]. The
  last seller fill has zero fee and PnL, hence no new cash journal event; its
  confirmed fill and cumulative .01 order-fee evidence remain present. This
  finite partial-fill case provides no throughput evidence.

The actual timeout/taskset prefix exits0 and is reaped after3,796,115,108ns.
Result stage is3.696681132s/4,857,651 observed logical bytes; final END is
3.758643664s/4,893,058 bytes. These stages are distinct, not latency or capacity
measurements. Original stdout is26,972 bytes, SHA-256
`56a9f75499a0a65c6cef7397cb8b7b440e25b470a93ad3d895de14d8ab5c6f45`,
with156 JSONL records (BEGIN,154 checkpoints,END); stderr is empty. Raw fits
512KiB including the512-byte failure reserve. Logical size stays below64MiB;
no kernel quota, blocked-I/O guarantee or fault injection is inferred.

All63 pins equal frozen Git, mini and before/after maps;61 native files equal
402c784 and18 loaded UTA origins are pinned. Actual CPU1, Python3.12.14,
SQLite3.53.1, executable fa674 and `-I -S -B` match. Runtime descriptors are
equal before/after; SQLite is builtin without an invented extension hash.
Forbidden imports are empty and final Python thread count is1, without kernel
thread or complete native-library attestation.

A review-only metadata comparison initially omitted the existing B
`actual_valid_IM_equality_risk` field from its expected projection and raised
an assertion (tool79d6b8). Its existing11-key source projection was added;
the complete comparison passed (3dde85). No provider artifact changed and no
target was rerun. A later review-file patch-format error was rejected before
writing; it likewise did not affect source, evidence or execution.

First PURE originals/3987, old7c8/fafd NOT_RUN records,6f finding,895 CODE,
plan92fc/c4e and23f materialization history remain protected. Three actual
FILL numerical replays pass but do not certify MM eligibility. Actual business
cases/profile and the independent manual oracle provide this narrow MM
evidence. The full admission replay model, broader compatibility, performance,
HA, real funds and production remain OPEN or unapproved. Perpetual funding is
unimplemented; genuine market publication was used. This review copies no
original case, database, source capsule, nonce or private ZIP bytes and grants
no additional execution permission.
