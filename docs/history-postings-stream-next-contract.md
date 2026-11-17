# Proposed repair after original red: two cursors, NOT_IMPLEMENTED / NOT_RUN

The [first attempt](history-postings-stream-attempt-01.md) reproduced all four declared UTF-8 prefetch error-order regressions. Its candidate/runtime/raw results stay frozen. This document requests a separately reviewed local repair, not an automatic retry authorization.

The replacement opt-in would use two full ordered queries in the original transaction:

1. `SELECT sequence,COUNT(*) FROM ledger_postings GROUP BY sequence ORDER BY sequence`: metadata rows contain only the original integer sequence and group count.
2. `SELECT sequence,ordinal,account,asset,units FROM ledger_postings ORDER BY sequence,ordinal`: payload rows are consumed **only after** the corresponding event's existing chain check, and only the exact count for that group. It must not call `next` for the next group's payload to discover a boundary.

Both streams remain in one consistent snapshot. Metadata can advance without decoding future account/asset/units TEXT. Missing current group yields the same original empty-posting normalization failure, without fetching a later group's payload. Every payload row must match the current sequence and original ordinal checks. Extra or residual metadata/payload fails closed under the explicitly recorded stricter unmatched-inventory policy. A truncated stream or count/sequence disagreement is an integrity failure, not a skipped group.

This targets **N to 2 SQL statement dispatches**, rather than the original N to 1 proposal. The metadata query adds a full posting-key scan; SQLite may do additional internal index work. Improvement is unknown and could be negative. Event rows remain the original `fetchall(N)`; only posting group/count metadata cursor consumption is bounded. It introduces no cache or cross-call retained proof, no new index/schema, no weaker guards, and no ownership/config/source shortcut. Automatic startup/final cold replay remain on the original default-off branch.

The exact same original multi-fault UTF-8 controls must pass, including first broken chain before same-group decode and first fingerprint failure before next-group decode. Tests must retain exact original exception type/text and failure priority. The SQL count test and measurement harness may change explicitly from one to two opt-in posting SELECTs only in the new candidate; original red inputs and output must not be overwritten. Missing/orphan/physical-order/ordinal/hash/unit/both-overflow/reference controls remain mandatory.

Root should first review a new immutable implementation and exact harness. Any next actual component requires fresh authorization and CPU coordination; it must retain the same total 15s cap, explicit source hashes, independent literal reference, all row counts, per-call SQL and logical/physical read distinctions, and final default cold reopen. The author does not self-approve performance or release acceptance. The catalogue/FK hardening group owns the independent old-catalogue gap; this proposal must not edit their files or portray the old gap as resolved.
