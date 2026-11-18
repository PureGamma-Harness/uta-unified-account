The first M05 push passed 2,049 unit tests on each of four Python runtimes, then failed the archive verifier because the sdist omitted two tracked public `inputs.sha256` provenance files. This draft composes the reviewed M0 controls above PR25/6010 and adds exactly two literal MANIFEST includes for those files. The `uta` business runtime tree is unchanged from 6010.

The branch carries the original M05 and general CI evidence through safe C933. Actual execution commit Mcad6 is not an ancestor, and the approved marker is absent from both the candidate tree and its history since source909. M05 remains B UNKNOWN / P NOT_RUN; registration05 is spent.

Validation:

- Package CODE SOURCE: `9cd87f7d0fbacdfd87a58dbef6ca24713dc3fe95`. Git/text inspection and independent CODE review confirm the two exact public blobs are selected and unchanged. No new package build, installed validation, SQL/native probe, or CI run has been performed for this source.
- Original run44217339023/attempt1 is preserved: four runtimes each passed 2,049 unit tests; compile/demo/replay/acceptance/formal/wheel steps succeeded; the exact-sdist check failed for these two files. Installed validation and review artifact steps were skipped.
- The earlier fixed d58 guarded suite passed 219 tests with six cold-import children. Its result remains source-bound. Actual M05's resource deadline UNKNOWN and all earlier first errors remain unchanged; no result is promoted to production, capacity, HA or real-money approval.

After root approves publishing this Draft, archive and installed verification on the new source must be recorded as new results. Rollback removes the two MANIFEST lines, or returns the control integration to the PR25/6010 baseline, while retaining every first-result artifact. This change deploys no service or schema and grants no further M05 execution permission.
