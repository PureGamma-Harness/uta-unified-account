# Cross enumeration inherited-pipe compatibility, v2

CODE_ONLY / NOT_RUN. The first source283dec8e execution remains FIRST_FAIL:
five methods/538 comparisons completed, then target os.fsync(1) on inherited
PIPE returned EINVAL and actual prefix/outer exits were1. Original13 files,
full vectors, seal and SAFE evidence4f4dd041 are preserved. No old run or
inner passed field is reclassified.

The only target code change deletes its final os.fsync(1) and os.fsync(2).
RawStream writes directly with os.write and has no buffered payload to flush.
The parent already writes captured bytes to its own regular raw files and
fsyncs those descriptors before calculating the outcome. Its exact EOF,
actual exit/wait/reap, strict status and late/short-write checks are unchanged.
No broad OSError catch, ignored error or success fallback is added.

All62 UTA modules, five methods/538 checks, independent oracle, numerical
parameters, scalar bounds, loaded modules, stages and vector assertions remain
unchanged. Of the67 frozen target inputs, only the entry byte hash changes.
The target plan is rebound to that one new pin. Of the parent's70 inputs,
only that entry and the target-plan byte hash change; the parent code and
its terminal acceptance logic are byte-identical. Existing536/4ac plans are
untouched. Historical target f51c0f68 and parent add0f4a6 metadata are copied
as exact pre-run bytes under first-283dec-FIRST_FAIL; their original internal
CODE_ONLY/NOT_RUN labels are retained as historical fields, not altered into
new claims. The actual first failure is established by4f4dd041 and RAW review.

The new target/capture namespaces contain pipe-v2-once01 and cannot reuse
the first62ada roots. Whole-host CPU1, target20s/parent22s cooperative window,
shared32KiB, parent512KiB and combined final logical8MiB remain unchanged.
These are not hard native-I/O or peak-disk/RSS guarantees. The exact new
source/target plan/capture plan/literal argv need independent delta review
and a separate root GO. No target import, compilation, test, SQL, process
probe, signal or execution occurs during this preparation.

A later run may compare complete vector groups with the old538 archive,
excluding invocation source/plan labels. Equality would not relabel the old
failure or establish joint borrowing, full model, performance or production
acceptance. Remove only these test/control changes to roll back; preserve all
first evidence, historical plans and confirmed financial history. No schema,
financial rule, account-authority or real-funds activation is introduced.
