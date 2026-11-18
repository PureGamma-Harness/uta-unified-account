# Independent integration CODE review: one CI-blocking test binding

**NOT_CLOSED_FOR_FIRST_NORMAL_CI** at immutable source
`ce8b497685c5c661e0b2a9e36f7367d2de3d60a6`, tree
`42afdc57f2e74ff948ca08c72f1420e99bcd043c`. The code integration parent is
`8b8eb7c9`; baseline is PR35 `9b61e5f`. This review reads Git source, physical
bytes, AST and JSON only. It does not import or compile target bytecode, run
tests/SQL/workers/CI, inspect processes, signal, or change the root worktree.

## INTEGRATION-TAG-PINS-001

Normal discovery calls
`LeaseObservationTagArtifactTests.test_complete_artifact_includes_tag_member_and_loaded_class_code`.
At tests/test_credit_lease_observation_tag.py:41, absence of the special
`_RETAINED_UTA_SOURCE_PINS` global selects the historical PR44 once plan. That
plan has SHA256 `8f12dd7a2ad9faabf4981499dee4bf011111273a48bf797678053dbc684ee726`
and61 retained UTA hashes. Ordinary tools/run_validation.py discovery does not
inject that global. The test then requires exact equality between this old map
and the newly generated artifact's current source map.

Exactly two expected hashes differ from the integrated Git tree: ledger.py and
service.py. The Enum fix itself is retained correctly. Therefore successful
current artifact generation cannot satisfy this old-map equality assertion.
This is a deterministic source-inferred test compatibility defect, not a newly
observed CI failure or evidence that the artifact codec rejects the Enum.

Preserve the historical plan and frozen override's exact validation. For normal
discovery, derive the expected map independently from the current canonical,
regular runtime files, with an explicit source inventory and stable before/after
bytes/metadata. Do not call the production artifact source helper to manufacture
the expectation, rewrite historical hashes, or relax the codec, exclusions,
unknown-object negative controls or required functions. A revised immutable
source needs a separate delta CODE review before its first normal CI.

## Other integration checks

- All61 physical root UTA Python files matched the reviewed Git bytes at the
  review point; none was missing. Only four UTA paths differ from the baseline.
- Ledger's new sequence-guard AST matches PR43. Replacing only that guard in
  the baseline produces the integrated full-file AST; the existing unit_digits
  replay interface and durable additions remain intact. Whole-file or entire
  replay-method identity with main-based PR43 is intentionally not claimed.
- Service's normalized AST returns exactly to the baseline after removal of
  the new helper, ordinary-admission projection branch and fresh ordinary-fill
  guard. Original RO handling and confirmed-ID early returns are unchanged.
  The extra projected risk evaluation adds work and can cause a configured
  freshness check to reject later; neither capacity nor compatibility of every
  previously accepted input is inferred.
- Startup and writer_fence are exact PR44 component bytes. Their finite Enum
  identity, primitive observation containers and existing Enum codec branch
  support the intended fingerprint shape by source inspection. The artifact
  validator, exclusion list and financial module inventory were not weakened.
  Actual loaded-runtime success still requires testing this combined source.
- The corrected Cross fixture matches b4e1b590 and retains the real read-only
  descriptors. The native SH fixture and fault test match PR45, and its fixed
  durable_process digest matches the unchanged runtime file. Its context change
  is per-router and restored; its extra SH descriptor remains instrumentation.
  No uninstrumented kernel-recovery claim follows from this check.
- D2_COMPANION_EXPORT_ENABLED remains literal False. Workflow, build metadata
  and MANIFEST are baseline bytes. Existing patterns cover the added source and
  finite evidence extensions; no wheel/sdist binary was built or inspected.
- The two earlier private profile-ZIP commits are not ancestors. Existing
  artifact/source bindings still require a fresh synthetic authority; no live
  authority hot-swap, migration or binding bypass is approved.

Historical component plans have different scopes. The full61-file tag plan is
stale for this integrated tree, and full native plans require changed inputs
to be rebound before execution. A selected pure Cross plan can still match its
narrow unchanged subset; that cannot establish full integration or actual
admission. No component PASS is reused as integrated acceptance.

PR45's ordinary publication router_busy remains unexplained. PR46's original
descriptor errors and separate capture-undo failure remain original failures;
the latter precedes the five-second recovery checks. The proposed STOP-ack
fixture, funding, expanded audit, reserve cache and snapshot selection are not
part of this candidate. H1 custom live AuthDB probes remain outside this task.

After the single test binding defect is corrected and reviewed, root can select
the first normal CI and synthetic acceptance for the new SHA. Preserve first
failures and actual runtime/source evidence. Production, real funds, sustained
10000/s, mixed/long loads, replicated durability and disaster recovery remain
NO_GO. Rolling back review documents changes no financial state; preserve all
confirmed history and prior artifacts.

Review preparation had read-only missing-path results for guessed control
filenames and one input-manifest attempt with an incorrect native-plan directory.
Git inventory supplied the actual handshake path; that assertion/read failure
occurred before writing the report. No target ran and no root source was restored
or changed. Only this separate, newly created report worktree was initialized.
