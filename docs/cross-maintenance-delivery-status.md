# Cross maintenance boundary delivery

The earlier investigation records remain historical preparation and first-run
facts. Their pending/no-SQL statements are superseded by this delivery status
and the independent first-SQL review; they were not rewritten after execution.

Configured Cross and the existing legacy service now require projected equity
strictly above maintenance margin for a fresh ordinary order or fill. The
existing initial-margin check runs first. Equality returns the existing
`insufficient_margin` HTTP409 contract. Reduce-only treatment and previously
confirmed order/fill ID lookup retain their prior behavior. This implements
local rule `UTA-CROSS-MM-STRICT-001`, not an externally certified exchange rule.
One additional full projected risk calculation runs on qualifying ordinary
admission; performance is not accepted.

At source `402c78412df53cb91e0f7f7d463fdd7026cf7cac`, the unique pure run passed
six methods and fifteen recorded manual cases. At SQL source
`e707fc55e83f53d79aa27610ea8f7b6386f6c713`, the unique first native run passed
three fresh authorities: five recorded matches/ten paired fills, an exact-MM
fresh rejection and second-side settlement rollback, legal zero-IM-availability
trading with lower MM, reduce-only close, cumulative partial-fill fees,
known-ID retries/conflict, three reopens and strict ledger/matching checks.
The actual caller observed exit0/reap in 3.796115108 seconds. These are finite
functional cases, not load, crash, HA or production acceptance.

Independent CODE/RAW reviews are included. Start with
[the independent SQL review](cross-maintenance-independent-first-sql-e707fc5-review.md)
and [the preserved SQL evidence](../evidence/reviews/cross-maintenance-boundary/first-sql-e707fc5-SAFE/README.md).
The full private eighty-file set, databases and archive are not public Git
deliverables. The public examples contain synthetic data only. Historical
replay checks numerical risk calculations; it does not independently prove
all admission eligibility or record the new projected admission decision.

## Deployment and rollback

This branch is based on PR35 `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`;
current main does not provide this configured Cross service. First integrated
CI at `fc2d574d` failed in all eight unit jobs (push44275550971 and
PR44275682105). The inspected original push3.12 unit ran2055 tests with four
errors: its new fixture assigned read-only service properties. The earlier
selected-method harness omitted those descriptors, so its pure PASS did not
prove normal unittest fixture compatibility. The corrected fixture initializes
the actual backing fields, checks both real property getters and rejects
assignment, while the revised pure scope retains both original descriptors.
The old first plan is preserved byte-for-byte. This correction changes no
financial runtime, database evidence or prior outcome; its tests are NOT_RUN
pending independent review. Keep the PR draft and real-funds enablement blocked until
independent release review and explicit launch approval.

There is no schema migration. First deploy to a new synthetic, code-bound
authority, preserving source, rule, market snapshot and command references.
Do not hot-swap the binary of an existing code-bound authority. Any existing
authority requires its separately verified writer handoff and artifact
compatibility procedure. Quiesce new admission, resolve unknown command IDs,
drain/retain accepted orders and checkpoint/reconcile before a replacement.

Rollback uses the prior reviewed deployment after the same writer handoff.
Preserve confirmed fills, positions, orders and journals; do not delete their
history or resubmit an unknown result under another business ID. Reverting
this guard restores the known maintenance-equality defect, so keep affected
new-risk operations disabled until a corrected release is available.
