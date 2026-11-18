# PR40 first CI: exact head push failed; PR-event matrix succeeded

**The first exact-head push remains FAIL.** Its Python3.10 job failed one unit
test. Python3.11/3.12/3.13 push jobs succeeded. The separate PR-event attempt1
matrix succeeded in all four versions. These outcomes are retained separately;
PR green and one successful package report do not erase the push failure.

Head C is `a2434bdfe711ead1d202f6c1527e527f73e2dfa2`, Draft
[PR40](https://github.com/PureGamma-Harness/uta-unified-account/pull/40), base
`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`. The first observed merge ref
`9b22adddd07cad796eb042d2179d2a78a26b8f38` has those exact base/head parents;
its tree `fdbe93d1cb5d4be863cb64cead05014934283f06` equals C's tree. It is still
a distinct commit/qualification. PR successful unit originals were not downloaded
to expand scope; their result is GitHub attempt1 job metadata, with that expected
merge ref recorded rather than a claimed downloaded PR source map.

| Attempt1 qualification | Run | Python3.10 |3.11|3.12|3.13|
| --- | --- | --- | --- | --- | --- |
| Exact-head push | [44241282705](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44241282705) | FAIL | success | success | success |
| PR-event / expected merge ref | [44241334703](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44241334703) | success | success | success | success |

Both terminal snapshots were observed at05:12:40Z. Subsequent poll rounds were
149 and247 seconds apart; status polling stopped when terminal was recorded.
There was no rerun, fix, new push, workflow dispatch or local target execution.

## Exact-head first unit failure

Push job134589520971 used Python3.10.22 / SQLite3.46.1. Its original unit ZIP
artifact14400281526 is89541 bytes, SHA256
`f40438ac07ed26de922157137dc0fceb00f50436238623add809b7db6883b906`, matching
the provider digest. All three members pass CRC/size/SHA checks. Summary,
worker-result and unittest log agree:2061 tests,1 FAIL,0 ERROR,0 skip, exit1.
All367 before/after source hashes match Git C; source-clean flags and the test
log digest match. That map covers runtime/test/tool source, not docs/evidence.

The unique failed ID is
`test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`.
At `tests/test_durable_faults.py:1461` its assertion is:

`False is not true : read/stop races exhausted the bounded SH capture attempts`

This is failure of the bounded SH capture precondition. The evidence does not
establish reaching the later five-second recovery assertion, and does not
attribute a cause to the matching optimization. The twelve new selector test
IDs are individually present and `ok` in this same failed full-suite original;
the exact IDs are retained in the unit audit JSON. No counts are invented for
other jobs whose unit originals were outside the selected download scope.

## One successful exact-head package report

Only push/Python3.11 job134589521552's report-only artifact14400062101 was
selected:58938 bytes, SHA256
`5e704a255cda37b2c4f493af30037ebc42f7231415924530e20ef6bf186f4820`, again
equal to the provider digest. Its19 members pass CRC/SHA checks. The report
records all seven archive checks true, no missing/mismatched files,62 runtime
hashes equal to Git C and the installed runtime digest, and all6885 tracked
paths in its required-file list. All22 changed delivery paths are included.
This is report-backed packaging evidence; no wheel or sdist payload was fetched
to independently unpack/recompute its bytes.

The installed report uses Python3.11.18 / SQLite3.46.1, source C, isolated mode
and unset PYTHONPATH. Its eight actual test IDs are `ok`, with8/0F/0E/0skip;
the eight recorded commands return0. All25 recorded module origins are in the
installed site, including `uta.matching`; helper/source/copy hashes agree.
This qualifies that single successful packaged default-path job, not the full
push matrix and not real-SQLite snapshot-mode settlement or throughput.

## Preservation and limits

Original provider metadata, two ZIPs, decoded job-log text and initial direct
download403 receipts remain private0700/0600. The direct redirect failures were
download-channel failures, not CI outcomes; authorized connector transport then
provided matching artifact bytes. The failed job log is explicitly labeled
connector-decoded UTF-8, not claimed original wire bytes. Signed URLs, keys,
nonces and arbitrary diagnostic payloads are not exported here. The safe JSONs
contain only directed metadata, hashes, identities and allowlisted assertions.

Two derived parser versions were retained privately: Python3.10 class-only
display and the installed nested `<locals>` class required ID normalization.
The v2 audits preserve the actual qualified IDs; these corrections changed no
original archive/log and did not rerun CI. Downloads stayed at one failed unit
ZIP/log and one successful exactC push package-report ZIP, under the respective
2MiB/1MiB limits and64MiB total private budget. Large wheel/sdist archives,
successful unit ZIPs and PR package payloads were not downloaded.

Review collected/read GitHub evidence and statically inspected archives only;
it ran no target/import/test/SQL/process fault, PID inspection or network probe.
Snapshot remains default OFF. New snapshot-mode SQL/settlement/performance,
production activation and real funds remain outside this evidence. No actual
matching smoke or benchmark was authorized or performed by this task.
