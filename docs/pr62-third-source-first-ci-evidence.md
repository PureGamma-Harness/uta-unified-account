# PR62 third-source first ordinary CI evidence

**Ordinary CI: SUCCESS. Independent RAW review: PENDING. Release qualification:
null. Production, real funds, HA, sustained capacity and duration: NO_GO.**

This is a separate first-attempt scope for source
`adb36877fb6bdb91db544dabda7f0d8cbc07d26f` (C). The provider's commit-filtered
list contained two runs: first push `44348761750`, created 16:34:18Z, and first PR
`44348776759`, created 16:34:23Z. Both were fixed while in progress and retained
through their first terminal success, at 16:43:20Z and 16:43:21Z respectively.
No CI run, failed job, source or artifact was rerun or replaced. The two earlier
failed-source scopes and their sealed originals remain untouched; this success
does not rewrite either failure.

## Actual ordinary CI and method observations

Terminal jobs and artifact endpoints were read once per run, after completion.
Eight jobs, Python 3.10–3.13 for each event, contain **200 successful steps**.
All eight original job logs contain exactly one unit validation JSON reporting
**2,194 tests, zero failures, zero errors, zero skips and worker exit 0**. Their
source-clean-before, source-clean-after and unchanged-source fields are true.
These aggregate job summaries do not establish eight complete method archives.

Complete unit ZIPs were collected for the fixed push Python 3.13 job
`134958285187` and fixed PR Python 3.13 job `134958348799`. All 22 distinct
methods in `test_market_transition_pending.py` and
`test_market_transition_activation_failures.py` have one strict same-line `ok`
in each log: **44 fixed observations**. The strict whole-log syntax counts are
2,165 for push and 2,166 for PR, separate from the reported total of 2,194.
No extra matrix archive or substitute green job was selected.

The following third-source methods each have strict same-line `ok` in both
fixed logs:

- `test_approved_ordinary_delta_does_not_allow_other_ast_edits`
- `test_complete_original_ast_is_preserved_except_exact_failure_hook`
- `test_capture_failure_is_one_shot_and_original_recovery_ast_is_untouched`

These are method completion observations. The ordinary unittest output does not
provide a separate subtest callback count, and none is invented. The earlier
readiness, partial-publication and exact-original-source/code-object methods
also have same-line `ok` in both logs. The native shared-gate horizon method has
an interleaved private diagnostic followed by standalone `ok` before the next
method, recorded as **INTERLEAVED_METHOD_COMPLETION_OK**, not same-line plain
`ok`. The selected logs contain no recorded FAIL/ERROR traceback. This remains
limited to these two complete archives; it does not retroactively resolve a
historical native failure or establish a separately controlled native capture.

Custom pure5/SQL17 component receipt capture remains NOT_RUN. Ordinary unit
completion does not substitute for that distinct receipt scope, financial
fault-recovery evidence or production acceptance.

## Source and provider bindings

Each fixed complete summary contains 410 before and 410 after source-map
entries. All four maps match each other and C's Git blob bytes and SHA256:
**1,640 tuple comparisons**, without importing or executing target code.
The exact runtime inventory remains 66 files, 65 Python plus one HTML, totaling
1,470,877 bytes. The explicit inventory V3 was inspected as AST data and has
those exact 65 Python paths. Runtime, tools, benchmarks and workflows are
unchanged from source8faa; two test files changed. Three runtime files differ
from base `ef7508bebd35cac71d9db8fdda896806ce4ade64`; the other 63 are unchanged.
C has 7,836 tracked files totaling 223,903,441 bytes by Git metadata.

The fixed PR logs identify actual provider merge
`f97b2c458ea22d10c405ba8eb1068e884defabc1`. Its retained provider metadata gives
parents base and C, and tree `e89231e65548c7f670a1a5908059f9ec802fc511`, equal
to C's local tree. Local merge-object availability is separately recorded in
`source-bindings.json`; it is not inferred from provider metadata. PR metadata
also identifies head C and base as above. No Git network fetch was performed.
Source pins do not themselves qualify installed binaries.

## Package reports and the one retained binary ZIP

Both terminal artifact inventories actually contain twelve artifacts: four
unit, four small package-validation and four binary-release ZIPs. Selection was
fixed to the two Python 3.13 unit archives, the **same push Python 3.13** small
package report, and one binary-release ZIP from that push. No other release ZIP
was downloaded.

The one binary artifact is `14447932492`, `uta-wheel-python-3.13`, exactly
54,775,150 bytes, outer SHA256
`5b89e784363b96fb5b23e57f5a71fdcf9f1b43e2825e5b6b415fcf408b21df5f`,
matching retained provider metadata. Its central directory has two entries.
Their names and declared sizes agree with the small manifest: wheel 397,373
bytes and compressed sdist 54,607,221 bytes. **Neither member was opened or CRC
verified.** Wheel contents/RECORD and the complete gzip/tar stream were not read.
An outer ZIP hash or member size is not an inner content identity proof.

The small package ZIP contains nineteen retained files. Its actual manifest
reports archive checks successful, source C, a 66-file runtime hash map equal to
C's Git bytes, and 7,836 required sdist paths equal to C's exact tracked path set.
The runtime-map digest was independently recalculated as data and agrees with
the installed report. These are validated report fields, not local verification
of the unopened binary members. Reported inner archive SHA256 values remain
explicitly labeled unverified against actual member bytes.

The installed report records eight tests with zero failures/errors/skips,
eight command return codes 0, and eight same-line `ok` observations in the
retained installed CLI log. The copied test-helper hash matches C's
`tests/test_durable_cli.py`. The finite SAFE projection publishes module names
and public source identities; actual installed paths, site/sys.path values,
arguments and runtime bindings remain private. The reported interpreter field
is the same public Python version string already recorded in both fixed logs.

Its direct module list has **25 names**, excluding `uta.funding_local`,
`uta.funding_obligations` and `uta.perpetual_funding`. Direct installed funding3
coverage is therefore OPEN. Candidate/independent-oracle direct installed
functional coverage remains NOT_VERIFIED. Neither the ordinary CI success nor
the small installed report closes these gaps.

No independently approved complete wheel/tar reader is available in this scope.
The historical static draft's exact executable identity is UNKNOWN; it was not
executed or treated as a budget proof. Actual binary qualification remains
NOT_VERIFIED and release qualification remains `null`.

## Pre-read limits and actual read accounting

Limits were fixed before provider/artifact collection: 128 MiB retained raw
data, 256 files, 8 MiB per provider/job-log response, 64 MiB per downloaded ZIP,
and 16,000 ZIP entries. Actual source/run identities were filled from the first
provider reads and fixed before terminal. A shared 8 MiB cap for unit and small
report output was fixed before their expansion. Separate release-layer caps
are outer ZIP member output 64 MiB including repeats, wheel output 4 MiB,
complete raw gzip/tar stream 256 MiB including headers/PAX/padding, and visible
sdist payload 223,903,441 + 4,194,304 bytes. Those limits do not authorize a new
unreviewed reader or imply that absent reads passed a qualification gate.

The reviewed stable small-data helper was rebound only at SOURCE and SOURCE_TREE
constants for C. It was used as the collector's own data transport/ZIP reader;
no UTA module or target test was imported, compiled or executed locally.
Three small ZIPs have **25 unique member reads, zero repeat reads and 1,711,948
expanded bytes**, all CRC verified. Extracted-copy reads do not re-expand ZIPs.
The binary ZIP had metadata reads only: release member payload output 0,
wheel output 0, complete raw tar stream 0 and visible sdist payload 0. Download
stream SHA and final sealed-file SHA are separate nonexpanding raw passes.

Before any artifact read, an initial static map candidate omitted two source
directories and three root files. Reading the exact validation source corrected
the expected-map data from 374 to 410 paths. Actual CI maps were subsequently
checked independently; no target, provider or CI retry resulted. This is an
administrative source-scope correction, not a target failure or repaired test.
After sealing, the first finite privacy check misclassified that interpreter
version string as a private path. Exact equality with both public unit Python
version fields established the narrow exclusion. All actual path/URL/identity
checks remain in scope; no additional archive member or CI operation was read.

## Sealing, delivery and rollback

Fresh originals are sealed as regular files `0400`, directories `0500`, with a
separate private name-bearing index. Public opaque inventory contains only
IDs, sizes, SHA256 and modes. Provider originals, download references, full logs,
actual runtime identities, ZIPs and installed paths remain private. The public
projection is finite; independent RAW review is still PENDING.

This commit contains evidence, its data reader and read budgets. It changes no
runtime, financial rule, schema, test, workflow or product activation. Rollback
is reverting these new evidence files; sealed originals remain retained for
audit. No local target import, compilation, test, installation, SQL, worker,
native actor or process/PID inspection occurred, and no CI rerun was requested.
No financial migration/reconciliation, sustained 10,000/s, 30-minute/24-hour,
HA, production or real-funds acceptance is claimed.
