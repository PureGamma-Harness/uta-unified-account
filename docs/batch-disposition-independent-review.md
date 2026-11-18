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

## Independent finite reference

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

Preparation froze the source before one separately root-authorized CPU1 / 10s
pure batch. Commit `46072191a265acfccee932e7e0bb5e9ea8dd2404` corrected the
preparation's check-count arithmetic from 1,794 to 1,694 before any execution;
the reference source itself did not change. The first execution ran all eight
methods and **1,694 checks successfully**, with zero failures/errors and exit 0.
Unittest reported 0.048s; measured outer elapsed was 120,249,199ns. All four
source pins matched before and after. CPU1 was requested through the saved
taskset command; this review did not independently sample child affinity.

The exact original stdout (299B, SHA256
`06cd025e9ddce45d8cab7b0f6a53a2a57b761e6efff667156ae288c2d1e73e1b`),
stderr (1,384B, SHA256
`75531b1c5c6a4bed616c842bb1498f1e910e1918ee4f164c5a4c116066b5205c`),
intent and execution are retained in this review's evidence directory. The
first private originals used exclusive creation and 0700/0600 protection.
No author or baseline test was rerun. The existing fixed-source manifest's five
payloads match their size/SHA pins, all four original source pins match frozen
Git blobs, and all eight baseline rows still retain six controls and two RED.

This closes independent CODE and bounded pure-contract verification of these
two added checks. Actual SQL/native recovery, UTA module-import, full-suite,
capacity and production acceptance remain open. The model assumes immutable,
fully established, unique member order and aligned current rows supplied by
the reviewed callers. It is not a general malformed-container parser proof,
arbitrary runtime callback proof or new test of SQL terminal immutability.

## Deployment and rollback boundary

No schema or persisted-format change is introduced. Rollout must preserve the
original immutable manifest/outcome when a stricter check refuses it and stop
for investigation; no automatic repair is authorized. Disabling new batch
selection retains recovery obligations for existing attempts. Reverting the
runtime repair weakens validation and cannot qualify an impossible old record.
This independent evidence alone grants no deployment or financial approval.
