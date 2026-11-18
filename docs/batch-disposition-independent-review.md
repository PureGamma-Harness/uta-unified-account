# Independent committed-disposition review

Candidate owner source is `711765a9a003e5c9ad871e59a6db067f0c3463e0`;
the runtime repair is `ff07673fcecfd25fa7df9aa212a710801142a799`.
This independent worktree changes no candidate runtime, author test or prior
first evidence. The existing two baseline RED and fixed 26-case result remain
unchanged. No SQL, UTA module import, writer, worker or authorization diagnostic
is part of this review.

## Code and compatibility evidence

`BatchStore.process` visits immutable membership once in order. It appends an
execution only after the original `QueueStore._execute` returns. Backoff,
existing terminals and earlier pending account heads can skip a member; control
and soft-budget barriers can end the loop. The execution list therefore need
not be a prefix. The repair's ordered-subsequence rule matches this control
flow without rejecting valid gaps or the empty list.

`QueueStore._execute` writes only SUCCEEDED or REJECTED and requires exactly one
PENDING transition. `QueueStore.record_failure` returns before touching any
already terminal row and its technical UPDATE also requires PENDING. Its
QUARANTINED transition is separate from the batch's `_execute`/append path.
The registered `uta_command_inbox_terminal_immutable` trigger prohibits updates
when OLD.state is not PENDING. Thus a prior quarantine may remain in the
disposition without being claimed as a new execution, and an executed S/R
terminal cannot legitimately become Q later under these reviewed paths.

These are code facts under the existing queue/fence/schema contracts. This
review does not execute or newly establish their SQL enforcement. It does not
claim that any rejected historical record or duplicate financial effect has
actually occurred.

## Independent finite reference, not yet run

The new reference uses four synthetic members and six possible per-visit
events: observe existing P/S/R/Q or complete a new S/R business action. It
constructs append-only visit transcripts for 1,296 histories. It separately
hand-lists the 16 legal observable words and compares all 65 permutations of up
to four members. This reference does not call the production validation helper
or copy its subsequence algorithm. The actual selected method AST is evaluated
only as the differential target, with an independently implemented canonical
JSON wire encoder and independently specified terminal state vocabulary.

Eight new methods plan 1,694 checks, also covering future progression of all
four recorded-PENDING members (256 combinations), immutable terminal mismatch,
preexisting quarantine, claimed quarantine, duplicate/foreign CIDs and existing
wire rejections. Explicit manual examples retain a valid nonprefix execution
and reject its reversal. This is new independent coverage; the author's tests
and baseline fixture will not run again.

Source is frozen before a requested single CPU1 / 10s pure batch. No target
execution has occurred at this preparation commit. Actual SQL/native recovery,
module-import, full-suite, capacity and production acceptance remain open.

## Deployment and rollback boundary

No schema or persisted-format change is introduced. Rollout must preserve the
original immutable manifest/outcome when a stricter check refuses it and stop
for investigation; no automatic repair is authorized. Disabling new batch
selection retains recovery obligations for existing attempts. Reverting the
runtime repair weakens validation and cannot qualify an impossible old record.
This independent evidence alone grants no deployment or financial approval.
