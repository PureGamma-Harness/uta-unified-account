# First full-matrix failure: independent read-only review

The first execution remains FAIL. Safe evidence commit
`8ad9bf67e8890489b5276a319b7e41845a5c4b7b` preserves its original reports,
identities, and all 16 traceback sections. The complete private raw log is
260,921 bytes, SHA-256
`fe173f0d54c176c4cd1d47e64e37d7f75b08d943b4eb89ad89aad1f29662db81`.
The independent `verify_original.py` first read passed all 12 checks. Private
originals were opened with O_NOATIME; their byte identity and unchanged file
stat fields were checked. No SQL, test, fault process, signal or QA was run.

Python 3.10 reported 1,804 tests, zero failures, 16 errors and zero skips;
summary and worker agree. The standard parent duration is 409.968156191s.
Each of the 16 original error sections contains one FileNotFoundError naming
a public Git-tracked file under docs/ or evidence/. The one import error is
the capacity-review reference module. Its frozen source contains ten test
methods; replacing those methods with one loader error explains exactly the
nine-case difference from the planned 1,813. This does not count those ten
methods as executed or passing.

The outer result is FAIL, exit one, no watchdog, reaped QA leader and unchanged
source/executable. Python 3.12 and 3.13 have neither result records nor output
directories. The saved supervisor launch identity matches the original kernel
exit observation: PID 462713, birth 8733529, matching boot, state Z under PID 1,
encoded status 256 / exit one. END and post-END retain an incomplete outcome
and planned exit one. The known PID1 zombie is not described as reaped.

The observed errors establish an incomplete input setup: the 874-file plan
covered six directories while tests also read public docs/evidence inputs.
They do not establish that all otherwise unexecuted paths would pass after
materialization, nor explain or resolve the earlier PR22 SQLite/publication
failure. A later all-tracked setup must use a different output directory,
preserve this failed run, and receive independent review and execution approval.

## Narrow review of the separately proposed tracked closure

Commit `e41861d582b73610342164a76e3fb6104f023717`, controller SHA-256
`b66632ccf60e61ceecd23394fc6cf41eaeeb0bb413df039d28fc74c2ffc9a594`,
changes the outer input inventory to all Git-tracked paths and uses the new
`6b7d473-tracked-closure-once02` output. The unchanged standard runner retains
its separate, byte-identical 351-file map. All controller functions except
the input inventory and prepare-output printing are AST-identical to the
previous revision; fixed source, CPU 4, runtime order, 900s active / 2,730s
whole budgets, GO, loader and completion rules remain unchanged.

The independent closure checker passed all 16 read-only checks on its first
run. The 6,162-entry inventory matches the frozen Git object IDs, modes and
sizes: 169,680,991 logical bytes. The retained after-materialization SHA-256
map equals the prepare map. The original 877-entry private baseline hash was
verified with O_NOATIME and all 877 before-byte hashes match that retained
after map. The source files themselves were not reopened. Zero changes to
their after-stat fields are the author's recorded observation; a complete
separate after-stat table was not retained, so this review does not claim an
independent before/after stat recomputation.

Fresh admission recorded 18,037,989,376 free bytes against the required
17,881,567,232 bytes. It authorized restoring only 5,285 missing tracked files,
with 164,827,136 conservative allocated bytes. Afterward 17,880,358,912 bytes
remained, above floor plus reserve. These are retained admission observations;
the controller must still check resources before executing each runtime.

The first-failure evidence subtree is unchanged. The new output did not exist
at this review. The author's new pure suite and prepare were read as retained
evidence, not rerun by this reviewer. No new QA, SQL or signal was executed.
There is no remaining specific static blocker in this input-closure change;
root must separately authorize any new-setup execution. That future outcome
cannot replace the first FAIL or establish the old CI cause or production
acceptance.
