# Independent delta review: pipe-V2 terminal fix

**CROSS-ENUM-ENTRY-002 CODE CLOSED for the new pipe-V2 source only.** Reviewed
code `a083fbc99d9e82d445b60d255a8872be41a8fb72`, tree
`d0cf49fdebd0f17f726d64ecfb1754b1c9a7ff59`; metadata HEAD
`bb2a2cf13a7337d4b6ef9f35ce2335c5732ad85c`, tree
`872856f0e4932db730aae048c1318ae0e6745819`. This is a Git/text/bytes/AST-only
review. No target import, compilation, test, SQL, process/PID probe, signal,
source execution or child agent occurred. No execution GO is granted here.

## Exact fix and retained failure behavior

The entry differs from failed source283dec8e by exactly32 bytes: the two final
statements `os.fsync(1)` and `os.fsync(2)` are removed. Whole-module ASTs are
identical after removing those two statements from the old main. There is no
new catch, ignored OSError, fallback, altered comparison or successful result
substitution. Its direct RawStream os.write calls have no Python output buffer
to flush; pipe-byte completion and durability belong to the capturing parent.

Private JSON controls/vectors still flush and fsync inside exclusive creation.
The parent capture source is byte-identical to the original, including fsync
of its owned regular raw-file descriptors. Failures there stay sticky. Actual
prefix0, successful wait/reap, both EOF, vector/source checks, time/raw/resource
conditions and external actual host-exit evidence remain necessary. Internal
actual_host_exit remains null and positive status remains pending external
observation. The final inventory/fsync/deadline can still invalidate a pending
internal positive status. No terminal gate was weakened to accommodate the fix.

The original confirmed FIRSTFAIL remains bound to283dec8e, private originals,
owner SAFE4f4dd041 and independent RAW report
`2eeda6da2686fe572135bf8eff1e98b1f19d4ff6`. The538 old numeric comparisons do
not become an old execution-chain PASS. The withdrawn a175 terminal compatibility
assurance and the original reports remain unchanged. This delta does not reread,
rewrite, repair or rerun the old private originals.

## Frozen inputs and unchanged scope

All67 target inputs are canonical regular physical files matching their new
length/SHA256 pins and Git objects:1,354,720 bytes. Exactly the entry pin changes;
the other66 are unchanged. Entry is12,311 bytes, SHA256
`5b9315dab2650bcfb7cf21418c460f8abab539d995bb748d2cc3e9f614774ad5`.
Target plan is12,675 bytes, SHA256
`0cbd7949055592adbb811f92b281ba4e158bec300b56f8ae3278e2168f082c70`.

All70 parent input pins match canonical regular physical files and Git:
1,388,651 bytes. Only the entry and target-plan pins differ;68 remain unchanged.
Parent plan is25,026 bytes, SHA256
`405da5ed431e926e9665e18ebed6d60851bd0135859c4526c962757e9c7b6739`.
Original targetf51, parentadd0, exact-entry and CODE-static metadata copies under
first-283dec-FIRST_FAIL each equal their original283dec8e Git bytes. Their old
NOT_RUN fields are historical preparation labels, not reclassification of the
executed first failure. Source worktree was clean at this inspection.

All62 UTA files, fixture/tests, independent oracle, seeded inputs, five selectors,
512/6/8/8/4=538 planned checks, eight-module loading and numerical bounds are
unchanged. Normal-path six read-only Git control children remain separate from
the sole timeout/taskset target prefix. Whole-hostCPU1, target20s, cooperative
parent22s/drain2s, shared32KiB raw, parent512KiB and final logical8MiB are
unchanged; none is a new hard native-I/O or transient disk/RSS guarantee.

The new target and parent namespaces are distinct fresh pipe-V2 roots, observed
absent read-only at review time; old once01 roots are not reused. Literal final
metadata HEAD argv still needs root's exact unique GO. New first actual
exit/reap/EOF,538 vector comparison and independent RAW evidence remain OPEN.
No successful runtime, E2E latency, joint loan permission, full Cross or
production result is claimed by this code fix.

No deployment/data migration occurred. Rollback removes new test/control
changes while preserving all historical plans, first-failure evidence and
financial history. Production, service activation, SQL/matching, custody, HA,
capacity, real funds, insurance and ADL remain NO_GO. No main-worktree/index
operation occurred during this delta review.
