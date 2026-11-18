# Once02 launch preflight stopped before adapter execution

Root's distinct authorization for the c076 actual adapter was received, but
the first launcher stopped in its initial source closure: reading
`tools/probe_observer_v2_adapters.py` raised FileNotFoundError. No target probe,
null-device open, data child, pipe or filesystem adapter was started. The
intended new once02 output does not exist. No automatic retry followed.

The relevant worktree HEAD was
`c146dc94749ea1bb06474bbb4358b745dfe59ea6`. Its Git source objects still have
no diff from the frozen c076 inputs. A subsequent read-only inventory shows
both probe and emitter carry Git skip-worktree (`S`) and are absent from the
sparse patterns. The independent documentation cherry-picks did not change
those source objects, but the sparse worktree no longer materialized them.
The integrator omitted a materialization check after those picks. An available
Git object does not establish that the executable input exists on disk.

The first tool's combined traceback, exit1, original launcher source/hash,
phase and exact limits are retained under
`evidence/observer-compact-report-v2/adapter-once02-preflight-first`. The
combined output is preserved as returned by the command tool; it is **not**
mislabelled as separately captured original stdout/stderr. The launcher failed
before its O_EXCL intent/capture setup. This missing preflight evidence boundary
is explicit. No actual elapsed-time performance result is claimed.

The eight-file physical source closure did not complete and receives no PASS.
This is a failed launch precondition, not a failed native read1 result or a
successful adapter execution. Root was informed before any restoration or
relaunch; the existing native authorization is not silently treated as a retry
budget. Source materialization and any resumed/new launch require root's
explicit ruling. Preserve this first record, original once01/c9 and all pure
results. Production, capacity, financial and stability gates remain NO_GO.
