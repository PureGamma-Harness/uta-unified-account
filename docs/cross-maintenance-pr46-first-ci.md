# PR46 first CI and descriptor correction

Source `fc2d574d7ac434a214bf332649edf0d2effc2a8c` failed both first attempt1
runs: push44275550971 and PR44275682105, all eight unit jobs. Each job footer
records2055 tests, four errors, zero skips and worker exit1. PR3.12 additionally
records one failure; the other seven footers record zero failures. These are
the original eight decoded job logs, with no CI retry.

Two original unit artifacts were downloaded once: push3.12 `14414781552`
(99833 bytes, SHA256 d6498537f08028afe92bb4b47f3a7e75de7082edf8d65e15f9920590ba42421f)
and PR3.12 `14414244607` (101681 bytes, SHA256 d2cebe0c673359f68335aaf16e10e9b3dcfc64e12b0750a1869858b1f6e78b79).
All six ZIP members pass CRC. Each368-entry source map matches the exact first
head tree before and after testing. The PR merge87792e6d has the expected
base/head parents and the same tree as head. Worker metadata matches its
original seven-field baseline, by native type and value. No successful
package step or full qualification ran; qualification is null.

Both inspected units have the same four errors in the new Cross fixture:
assignment to the actual service's read-only `product_catalog` property.
The earlier pure harness selected six methods but omitted its property
descriptors, so that earlier PASS cannot establish regular unittest fixture
compatibility. The narrow fix `b4e1b590` initializes the backing fields, asserts
getter identities and rejected assignment, and retains both exact descriptors
in the revised pure scope. Financial runtime is byte-for-byte unchanged.
The original92fc36 plan is saved unchanged alongside the revised021639 plan.

The additional PR3.12 failure is the original shared-gate capture-undo assertion
at test_durable_faults.py:1456, before the five-second recovery checks. It is
separate from the descriptor errors; its cause remains UNDETERMINED. This
PR35-based source does not contain PR45's instrumented SH fixture.

Independent CODE568d8c3e closed the descriptor correction before its unique
first pure execution. That new source completed six methods/fifteen recorded
case completions, zero failures/errors/skips, actual caller exit0/reap in
229264668ns. Nine input files and plan bytes/metadata remained unchanged.
The original driver and caller output/receipts are copied exactly under
`first-pure-descriptor-b4e1b59`; the caller standalone program was not archived,
and its root exec input is not represented as a pinned standalone controller.
This is a scoped pure result, pending independent RAW review; post-fix normal
CI is not yet tested. No SQL was repeated or production approval inferred.

Twenty-four full private CI files total1431017 bytes, retained separately from
their PRIVATE-SEAL. All original unit logs, ZIPs, metadata and signed download
references stay private. The public four JSON files expose finite outcomes
and byte inventories only. The administrative oversized exec-argument rejection
and normalized-result parsing error are preserved in collection-notes; neither
started a target, redownloaded an artifact or changed original evidence.

Reverting these evidence files changes no financial state. Reverting only the
fixture correction restores the known test errors. Keep the financial guard,
confirmed trade history and private first outcomes intact. Production, HA,
real funds, sustained capacity and complete admission replay remain unapproved.
