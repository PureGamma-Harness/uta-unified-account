# PR36: first integrated CI and one package-report archive

Frozen source `db04e6cb0ddb3a015554621949b255abaad9a572` passed both first
attempt1 workflows: **all four push and all four PR whole jobs succeeded**.
This is engineering CI evidence for the source/sdist-only synthetic prefix
contract. It does not complete a forensic audit of the paused909 run or grant
financial, capacity, long-run or production qualification.

| Run | Event | First result |
| --- | --- | --- |
| [44222147210](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44222147210) | push | 3.10 / 3.11 / 3.12 / 3.13 whole jobs succeeded |
| [44222273930](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44222273930) | pull_request | 3.10 / 3.11 / 3.12 / 3.13 whole jobs succeeded |

[Exact job IDs and unit/package/install step conclusions](../evidence/reviews/pr36-first-ci/run-job-outcomes.json).
No CI run, test, build, CLI, SQL connection or business operation was executed
locally by this reviewer. No successful unit ZIP or decoded success job log was
fetched, so this report gives no content-verified unit-test count for eight jobs.

## Observation custody

Root transferred five original connector serializations: one run discovery and
two push/PR job observations. This review read them without refetching the
first discovery. Their original hashes remain unchanged. Root reported the
first discovery at02:18:53Z and the second job observation at approximately
02:23:55Z. The files were saved later: file mtime is not treated as request
time, and no continuous30-second sampling cadence is claimed.

This reviewer first fetched actual jobs at02:26:36.735–37.465Z: all push and
three PR whole jobs were already successful; PR3.12 unit had succeeded and its
remaining steps were running. The next PR observation established its final
success, and a terminal run query confirmed both workflow conclusions. Actual
request timestamps and root-transfer provenance are retained separately.
[Observation provenance](../evidence/reviews/pr36-first-ci/observation-provenance.json).

## Exactly one selected successful package report

The review used its authorized optional package check only for PR3.13 job
`134526800720`: artifact `14392325024`,
`uta-package-validation-python-3.13`, **54,636B**, SHA256
`389a95d782395a8b76b864cdd80825256caf8ab7c3d2e0099ebe209d1096fafd`.
One actual download matched provider size/hash. All **19** ZIP members passed
CRC and size/path/duplicate-name bounds; their individual hashes were recorded.
The full original ZIP
and reports remain private.
[Archive integrity](../evidence/reviews/pr36-first-ci/package-artifact-integrity.json).
The first artifact-metadata page returned twelve items; no other archive or
page was downloaded. [Metadata scope](../evidence/reviews/pr36-first-ci/artifact-metadata-projection.json).

The package and installed reports name actual PR merge
`b1f7848814bbcf7a79bfad553d8233ee59ae7f43`. Independently fetched provider commit
metadata binds parents `[6010e920…, db04e6c…]` and tree
`dabd6a40b0b874d698d05abd2f90f7907fc232ef`, matching the local candidate exactly.
The35 source changes contain no `uta/` runtime difference from base6010.
All **62** runtime digests in the selected package report individually match
the candidate Git blobs. The package helper, copied helper and frozen source
helper hashes agree. [Source binding](../evidence/reviews/pr36-first-ci/source-binding.json).

The original package verifier reports all seven checks true: version, wheel
runtime, sdist runtime, exact required files, pinned legacy fixture, licensed
legacy fixture and entry points. Its6,308 required paths match the full
candidate Git path set; missing/mismatched lists are empty. The required list
contains exactly once both `tools/prefix_contract.py` and
`schemas/completed-prefix-forensic-receipt.v1.json`, and the source MANIFEST
explicitly includes the latter. The tools API and schema are source/sdist
deliverables; this review does not claim they are installed UTA features.

These are content-verified **report** records and independently checked source
selection/runtime bindings. The wheel and sdist payload archives were not
downloaded, and this reviewer did not perform a second6,308-file payload audit.
[Package report projection](../evidence/reviews/pr36-first-ci/package-report-projection.json).

## Installed records from the selected CI job

The original isolated installed report records eight tests, zero failures,
errors or skips, and all eight test methods explicitly `... ok` in its retained
CLI test log. Its expected count is eight; unittest reported8.615s. Eight
recorded console/demo/acceptance/scenario/init/inspect/status commands have
return code0. Recorded module paths point to installed site-packages, isolated
mode is true and PYTHONPATH is absent. Original/copy/source helper hashes and
artifact maps agree between package and installed reports.

These actions occurred in the selected CI job, not during this independent
review. They exercise the existing installed UTA package; they do not perform
a completed-prefix forensic audit or qualify the source-only synthetic receipt.
[Installed projection and original method outcomes](../evidence/reviews/pr36-first-ci/installed-validation-projection.json).

## Scope, deployment and rollback

Prior25PASS, independent4RED and the later10-check result retain their original
source and scope. This new integrated source result does not erase the original
causality counterexamples or change any qualification flag. The paused909
six-hour and old88724h failures remain their original failures.

This OWN adds only public-safe evidence. Original connector responses, signed
download response, selected ZIP and reports stay outside Git in0700
directories with0600 files. Public data contains allowlisted metadata,
synthetic test names and source/report hashes; no key, nonce value, signed URL
or database is published. [Ownership and exact operation counts](../evidence/reviews/pr36-first-ci/review-ownership.json).

There is no runtime deployment, schema/data migration or service restart for
this evidence-only delivery. Rollback removes only these public additions and
retains all original evidence and financial history. Actual forensic evidence
collection, financial signoff, target-host qualification, sustained capacity,
HA/DR and real-funds approval remain open.
