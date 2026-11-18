# First full-matrix execution: NO_GO, input closure incomplete

The authorized first execution used source `6b7d473`, plan `7ec6f31` and
supervisor SHA256 `084a9aa9b1fa357c0f485ea92a19b9185948361f7740aeff16c5f84966b7dabd`.
It is preserved as a failed first execution and was not restarted.

Python3.10.22 / SQLite3.53.1 completed 1,804 tests with zero assertion failures,
16 errors and zero skips. Standard duration was 409.968156191s. Every original
error section contains FileNotFoundError for a public Git-tracked fixture or
reference under docs/ or evidence/. One reference module failed at import,
replacing ten methods with one loader error, so 1,804 is nine below the planned
1,813. The first outer outcome is FAIL, exit one, no watchdog, direct leader
reaped, source/executable unchanged. Python3.12 and Python3.13 were never started.

Supervisor PID462713, birth8733529, the original boot ID, was observed exited/Z
under PID1 with encoded status256, exit code one. END says not all three passed
and post-END records planned exit one within its budget. All 33 adopted zombie
child PIDs were absent in the later metadata-only check; only the supervisor's
PID1 zombie remained. No old authority was opened or signalled and no files
were filled in while this run was executing.

The input plan's 874 entries actually covered six folders and selected metadata;
that was not a complete QA dependency closure. The tests also read public
docs/evidence files. This is a setup defect in this plan, not a reason to alter
the first failure or label the original PR22 CI error as resolved. The next
proposal must materialize and hash all 6,162 tracked files from the same source
and preserve the standard 351-file source map separately. It needs a new output
directory, independent review and another explicit root execution GO.

The complete first unittest raw remains private, SHA256
`fe173f0d54c176c4cd1d47e64e37d7f75b08d943b4eb89ad89aad1f29662db81`.
The 16 full original traceback sections are copied without rewriting, with
original line ranges and individual hashes. Other copied files are raw standard
reports, identities and supervisor outcomes; their byte hashes are in manifest.
File existence or an END file is not a production or complete-matrix pass.
