# Independent first-CI compatibility CODE review

Decision: PASS_STATIC_NO_BLOCKER for candidate
1fd9ca0f3142bff87a8329e2a257dd5a7ca73227, exact parent
72dd3a17d7a8e363d95854ee8c4f361e0a24d901. This is a five-file test/fixture/docs
review. It is not a new CI result, native recovery result or production approval.
Root may use this source-level conclusion when deciding a separately scoped new
first normal CI. No target import, compile, test, SQL or process inspection ran.

The five changed Git blobs match the author worktree. All UTA Git paths match the
parent exactly. Four changed Python files parse as AST. No lease, timing, fee,
business threshold, skip or runtime financial path changed. The companion JSON
records exact lengths and SHA-256 pins. Historical failure artifacts, original
native/helper scopes and old authorities were not altered or reopened.

## Publication pause and original command

The test now observes the queued command through status immediately. This is
the appropriate nonterminal observation: router.wait polls until a terminal
receipt, absence or its deadline, and is not an immediate PENDING observer.
The existing typed market-transition marker makes process_one pass
allow_submit=False, which excludes submission rows before an execution attempt.
The new PENDING, attempts=0, result=None, error=None assertions agree with that
path, and the unchanged 12-table financial_snapshot checks committed financial
state while excluding queue metadata. Publication/explicit-halt rejection rules
are not changed by this test delta.

After exact replay and activation, the original CID is awaited as SUCCEEDED.
Queue execution stores the order dictionary returned by _admit_order, so its
order_id and positive reserved_margin accesses match the actual result shape.
The setup has healthy collateral and no executable opposite order, so no new
obvious background financial race is introduced by the duplicate snapshot check.
The duplicate helper uses the same account, command, order, quantity and price;
QueueStore.enqueue compares canonical content and returns the original row
without executing again. The later ordinary order is still exercised.

Nonblocking coverage note C1: the new duplicate assertion compares receipt.result
and the financial snapshot. It does not compare every outer receipt field such
as sequence, attempts or timestamps. The unchanged enqueue branch supports
original-receipt identity by static inspection; a full receipt equality assertion
would make that additional contract explicit in future runtime evidence. This
review does not describe the narrower assertion as an observed full-receipt pass.

## Offline control corruption and read-only diagnostics

The modified corruption test first closes its fresh synthetic router. Each
subcase takes the existing exclusive control lock and restores a copied valid
state. Bad halted/pause types must still raise ServiceError(control_corruption)
through normal _write_state, before its transaction, with valid state unchanged.
Only this closed test control database then receives a parameterized direct
payload UPDATE under the same exclusive lock. Its existing control transaction
role is the same path used by the normal writer; this is test fault injection,
not a production API or a relaxed validator.

Canonical JSON encoding matches the normal control encoding. Invalid halted,
pause marker, watermark index and market version/digest faults each fail
_diagnostic_state before state_observed is set or state is projected. The test
retains unready, state_observed=False, state=None, control_corruption and private
path-redaction assertions for all four faults. Diagnosis occurs after releasing
the exclusive lock; finally restores the valid original under a new lock.
No new live-corruption race or reentrant lock requirement was introduced.

## Native SH fixture binding only

RUNTIME_BINDING_REVISION is literal 2. RUNTIME_SHA256 is literal
9b346b3888a162141699926f6c4505b6804a5982a82af7ef3c017cac6ed1053e,
which matches the 110,134-byte durable_process Git source. PREVIOUS_RUNTIME_SHA256
equals the parent fixture's old literal. PROFILE remains the original SH v1
value, and wire messages remain version 1. All fixture function/class ASTs are
identical to the parent, including exact source hash, source compilation versus
loaded worker-code equality, unique reviewed callsite and one-shot trace checks.
Static AST inspection finds exactly one _run_worker and one view.process_one
call in that worker, at source line 544.

The pure test adds the literal revision/hash/history assertions without removing
its changed-source or changed-code rejection checks. No compilation was carried
out in this review. The existing trace/capture implementation, lease recovery,
timeouts and native assertions are unchanged. Changing the pin does not prove
the native horizon now passes or that its earlier failure had only one cause.

## Evidence boundary and next gate

The delivery document preserves the first eight failed jobs and distinguishes
the two fixed logs' 44 method observations from evidence for every job. Those
historical counts/log statements were supplied with the task and are not a new
collection or independent re-execution here. The document explicitly separates
the old child fingerprint mismatch from any claim of a unique horizon cause.

There is no static blocker to requesting a new first normal CI on this exact
candidate. New job outcomes must stand on their own immutable source/results;
the earlier failed run remains failed. Functional, installed-component, capacity,
HA and real-funds gates stay open. Rollback reverts this test/fixture/docs delta
without changing financial authority or confirmed effects; retain both historical
fingerprints, original failures and this independent review.
