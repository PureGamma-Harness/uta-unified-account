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
