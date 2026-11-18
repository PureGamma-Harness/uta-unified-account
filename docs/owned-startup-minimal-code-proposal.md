# Minimal next code: establish evidence before changing admission

Baseline witness `5af6cb0eead28c3fd23c921143bbda5a53ac53ea` is sealed first.
The three conditional RED do not prove the two real errors' histories. Phase1
below is now implemented at6303ed4, CODE-only reviewed and **NOT_RUN**; it is not
a permission to ignore expiry. The12/48 pure closure/driver identified by the
current `phase1-focused-plan.json` still requires its own static review and exact
root once budget. Preparations72dcebf/166ddf9 were NOT_RUN, with zero attempts;
their static findings are retained in `phase1-preparation-CODE-fixes.json`.
Phase2 is not applied.

## Phase1: observation-only patch, unchanged fencing

The smallest useful production change records facts already available during
existing calls, with no extra SQL, replay, status query, token renewal, retry or
clock extension. All added fields are private diagnostics and must never feed
authorization, READY, cached verification or automatic retry decisions.

1. At writer_fence._assert_token's existing lease_expired branch, attach a
   bounded immutable observation to the original WriterFenceError before
   raising it: version, used-row generation/observed_ns/expires_ns, sampled
   now_ns, clock-domain label and the already-established identity-match flag.
   Do not include raw authority/nonce/boot values. Error type, code, args and
   rejection condition remain identical.
2. WriterFence.renew already calls _load after its UPDATE for the renewed event.
   Bind that same returned row once; add no SQL call. After the original
   transaction context returns known success, expose a private observation on
   that **fence instance** containing generation/observed/expiry and known-reply
   status. Clear the attempt observation before starting; no receipt is known
   if BEGIN, UPDATE, event append or COMMIT/its response raises. A wrapper that
   raises after actual COMMIT still must not give its caller known success.
3. OwnedStartup._renew copies that private receipt only after its exact
   original renew call returns. Retain its last known receipt separately from
   the current failed/unknown attempt. This is telemetry, not a verification
   capability. Never convert the keeper's existing poison to healthy.
4. At owned RO entry failures, annotate the original exception with a constant
   phase and a snapshot of the bounded known-renew observations. Annotation
   failure must preserve the original exception. The same approach applies to
   verify_ledger and verify_credit; other sites remain separately identified.
5. The private test/worker failure collector may publish only an explicit
   allowlist of those typed integers/booleans/enums and clock labels. Current
   unittest text alone does not retain arbitrary exception attributes, so the
   collector must preserve them explicitly in a private artifact and safe
   projection. Keep raw streams and first exceptions unchanged.

These fields can distinguish an old used-row expiry from a known successful
renewal of the same scope: both recorded expiry and assertion now use the
fence clock domain. Monotonic keeper start/return observations are separately
labelled and must not be subtracted from an injectable/BOOTTIME fence clock.
No post-failure current-row read is presented as the original observation.

### First focused pure budget to request after code freeze

For a distinct observation-only source, request one CPU1/10s batch of at most
12 methods/48 small fake traces. Extract actual changed methods into a fake
connection/context namespace; do not import UTA or open SQLite. Check original
SQL strings/call order/count, unchanged current-token rejection, known COMMIT,
COMMIT-unknown, post-COMMIT wrapper error, preserved primary exceptions,
nonfinite/bool/extra-field filtering, immutable observation copying and absence
of nonce values. No native, worker, signal, process, network or real sleep.
Retain the first result even if RED. This budget is a proposal, not yet used.

The revised once driver binds the exact fixture and selected-source AST bytes
to the same eight materialized input pins before execution. Its independent
normal-load oracle records the original ordered SQL, complete parameters and
returned state rather than calling the current production helper to produce
an expectation. The source-selected renewal closure includes the unchanged
original `_ttl` with its passive `math` dependency. These are static preparation
fixes, not observed test results.

The frozen host argv uses `timeout --signal=KILL 10s`, CPU1 `taskset` and the
specified Python binary with `-I -S -B`. The driver independently records and
checks actual affinity, Python version/flags and executable length/SHA. Its
reviewed-stream capture reserves each UTF-8 write before writing FD1/FD2, with
one shared256KiB limit including a512-byte failure-trailer reserve. Oversize,
zero/failed writes become sticky incomplete capture and exit125. A Python trace
deadline exits124; the outer host deadline covers blocking/native interpreter
work and its actual termination status must be retained separately. No complete
test result can be inferred from an absent END/receipt or an UNKNOWN capture.
This is a guard for the reviewed pure closure, not an arbitrary-code OS sandbox.
See `owned-startup-phase1-focused-protocol.md` for the exact acceptance protocol.

## Phase2: behavior change remains behind a separate proof gate

An owned-RO admission primitive may eventually use a **known current live**
same-token control binding, exact snapshot identity match and a complete
financial-data stability obligation, then run the original full verifier.
The existing final fresh fenced COMMIT remains authoritative. This is a
different change from diagnostics and cannot be approved merely because the
baseline witness exists or the original error disappears.

Two alternatives require concrete source evidence:

- Enforce a persistent/composite watermark covering every mutable financial
  projection and schema. A ledger MAX(sequence) or account cache is inadequate.
  Its migration, every writer's update and all role restrictions need review.
- Prove equivalent exclusion for the exact private startup call graph: initial
  writer drain, same-PID actor exclusion before/after BEGIN, other-process
  fencing, allowed control/inbox/batch roles, and every owner-thread write
  between verification and final COMMIT. The current owned scope still allows
  its owner thread to open financial transactions; it is not itself a blanket
  no-financial-change certificate.

Without one complete alternative, replacing snapshot expiry with a fresh
lease check can certify an old financial view. No such runtime replacement is
included here. The global WriterFence._assert_token must retain exact expiry,
nonce/generation/PID/boot checks and no-revival behavior. Known current new-head
generation must never be mixed into an old-snapshot certificate.

Actual SQLite/WAL snapshots, keeper scheduling, writer contention, OS pauses,
original0.4s fixtures, genuine corruption and the final READY handoff need a
separately authorized native test after independent CODE/pure review. The
mathematical witness and proposed watermark policy do not supply this approval.

## Delivery and rollback

Current delivery contains phase1 observation code, docs, model/fixture source
and immutable first baseline output. Original tests, SQL operations, schema,
lease and financial decisions remain unchanged; phase1 pure/native/whole-suite
and packaging acceptance is not granted. Added guard/load/fetch/validation
timings affect all read TransactionGuards, so no timing/performance equivalence
is claimed. The original ERRORs and baseline RED remain original results.

Runtime bytes have changed. Existing code-bound authorities cannot accept an
unreviewed binary swap or marker rewrite merely because persistent schema is
unchanged. Any authorized execution must use a separately pinned fresh
synthetic layout until a financial upgrade/recovery procedure is qualified.
Reverting phase1 in Git removes telemetry, but is not a data rollback: retain
old authorities, original commands, receipts and financial history, and never
erase UNKNOWN state or reissue it under a new ID. Phase2 requires its own
deployment/migration/rollback plan and acceptance record.
