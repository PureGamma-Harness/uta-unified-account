# RUN-R5 package omission binding author fix

This follows R1–R4 candidate2e0af1e and the independent static finding OWN5df5602
(parent32c94f2). The original finding remains **static**: it established a
specific miswiring opportunity with another wheel that still contains the
removable member; it did not execute the collector or establish that a past
release used bad artifacts. Those original reports and package results remain
unchanged. This change hardens the unused runner, not financial runtime or a
frozen stability release.

Qualification no longer accepts two collector `passed=true`/exit1 labels as
proof of the intended omissions. The separate registration now also supplies:

- `artifact_files.wheel/sdist`: original physical paths and SHA references.
  Actual regular-file bytes are bounded/read and their **SHA and byte sizes**
  must equal the complete positive artifact manifest.
- `verifier`: the actual verifier file reference. Its hash must be the
  qualified source's `tools/verify_release_archives.py`. Negative command argv
  must name that verifier, exact source/commit and the two registered inputs;
  no unexpected flags, relative input paths or different positive side pass.
- `runtime_reports.wheel/sdist` and `zip_reports.<each tracked ZIP>`: separately
  pinned original primary-verifier JSON reports. These can be archived copies;
  the actual original/negative archive inputs must remain available at their
  recorded paths for byte comparison.

Both runtime directions must be distinct and present. For wheel omission only
`wheel_runtime_exact` may be false. For sdist runtime omission only
`sdist_runtime_exact` and `sdist_required_files_exact` may be false. ZIP-only
omission may fail only `sdist_required_files_exact`. Every unrelated boolean
must remain literal true. The case and raw report must agree on this complete
matrix, exact missing member, no mismatched source files, actual exit1, original
source/version/metadata/runtime map/tree and required-file/legacy/helper data.
The raw report's two input artifact names/hashes/sizes must match the actual
negative and unchanged original bytes. A copied source ID is insufficient.

The runner also reads each negative ZIP/TAR. Its logical member list must be
the positive list with exactly the target deleted, in the same order. Every
other payload hash, entry type/mode and retained metadata must remain equal.
Thus a full check matrix cannot conceal another changed runtime member when
the already-false runtime check would otherwise hide the difference. Container
headers/compressed offsets are not mistaken for source-member identity.
Positive archives are rechecked after the comparisons. Inputs are bounded to
128MiB per archive,64MiB per decoded member,256MiB decoded archive total and
20,000 members. These are read-only comparisons; no archive is installed or
extracted into a financial directory.

The new pure ZIP/TAR fixture tests include the exact necessary old-wheel
precondition (another version **still contains** failure_diagnostics.py),
extra false checks in each direction, a wrong unchanged-side hash, a different
verifier argv, missing tracked-ZIP proof, and a second modified payload even
after its SHA/report labels have been updated. They do not run a real old
collector or reuse an old artifact as qualification. Synthetic positive
records test the evidence contract; they are not provider or release evidence.

The R5+existing pure controls passed26 cases on each of Python3.12/3.10/3.13
in0.283/0.292/0.308s with ResourceWarning treated as error and forced GC.
Raw commands, timestamps, source hashes and logs are retained in
[`evidence/runs/managed-variant-runner-r5-closure`](../evidence/runs/managed-variant-runner-r5-closure).
No benchmark, service, SQL, build/install, profile or long job was run.

Keep execution NO_GO pending independent R1–R5 closure and new exact-source
full local/CI/package qualification plus actual cohost/reserve registration and
quiet-window authorization. Rollback restores the prior diagnostic checkout
in a new commit while preserving every red/control record; it never deletes
an authority, changes irreversible capability, retries unknown financial IDs,
or modifies the original stability jobs. Old six-group proof registrations
without physical package/report bindings now fail closed; prepare remains
side-effect free and the template GO remains false.
