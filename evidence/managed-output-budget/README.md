# Output budget preparation evidence

OWN worktree `/workspace/uta-managed-output-budget`, from immutable source
`8b7f544fcbdfd540d43de1d6560022c6ebbd3799`. That candidate remains NO_GO. Policy
and resolver were committed first as `ade1277`; the following implementation
adds the explicit-field policy without editing any old preregistration bytes.

`run_pure_tests.py` records exact sequential CPU2 commands. The final batch ran
36 tests on each Python 3.10/3.12/3.13, with zero failures/errors/skips and
ResourceWarning treated as error. Total wall time was 0.746 s. It selects no
original PIPE child fixture and starts no dummy, service, producer or SQLite
connection. Supervisor control-flow tests replace all children with mocks and
stop after one collection iteration. Sparse temporary files exercise byte-size
metadata without allocating GiB of contents. Existing prepare tests only use
copied synthetic profile/plan JSON. Fixture report test counts are synthetic
inputs, never actual source qualification claims.

The first integration batch was 20/20. The next 24-case batch preserved here
has one intentional permission-fixture setup failure: the caller's private
umask turned `mkdir(mode=0755)` into mode0700, so the negative fixture was not
actually invalid. Its log and exact source hashes remain unchanged. The final
fixture explicitly `chmod(0755)` before testing; production policy was not
relaxed. The final 36-case batch includes 24 budget tests plus six existing
pure long-launcher and six prepare cases.

`verify_default_compatibility.py` checks protected function ASTs against the
immutable base, the original `OUTPUT_CAP` assignment, the legacy three-file
measurement block (unwrapping only transparent output-write calls), and the
final financial/coverage/fault gate. All UTA files, old plans/profiles, coverage,
producer, observer and smoke core bytes listed in its JSON are unchanged. This
is scoped evidence, not a claim that the whole supervisor AST is unchanged:
explicit policy, registered-budget consistency and output-write handling are
new code. The historical `measured_known_output_bytes` event field and lack of
resource drain remain for plans missing the optional field. Explicit6GiB opts
into the new tree policy just as explicit2GiB does.

The new policy counts regular-file logical `st_size` in control and observer;
directory inode allocation and filesystem block consumption are not an OS
quota. Traversal streams entries with bounded directory depth and anchors
metadata using owned-output directory FDs. It never opens database file data.
Only the helper's direct recognized private clone directories are excluded;
their contents still undergo type/symlink checks, and unknown siblings count.
An atomic temporary entry disappearing during measurement fails closed as a
technical unknown and requests drain. This conservative policy may therefore
end a future attempt on a measurement race; no claim of eliminating such races
or improving performance is made. A private scratch ancestor is trusted under
the existing launcher contract; this is not a general whole-path authorization
proof. Failed log writes may prevent persistence, but cannot precede/suppress
the resource drain action. No unsafe force-kill, cleanup, restart or resume is
added. The 30-second collection-loop check can be delayed by synchronous final
helpers; overshoot is not bounded.

Exactly one permitted actual cohost metadata/proc/free observation was made at
2026-11-17T14:05:13.965287Z. Stable producer metadata and both original birth
identities passed then; effective heartbeat age was 3.937532983 s. Observed free
bytes20,648,210,432 minus the proposed16.25GiB total17,448,304,640 left an
arithmetic margin3,199,905,792. These reads are not a shared logical financial
snapshot or an allocated reservation. The old observer's declared byte cap is
unknown, its extra256MiB is only a contingency floor, and independent operator
approval remains false. Resource admission, candidate qualification and actual
execution authorization remain NO_GO/false. Recheck after the future exact
source's full3/CI8/package qualification. No new source profile is fabricated.

Reproduction from this worktree (read-only source/owned temp files only):

```sh
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -B evidence/managed-output-budget/run_pure_tests.py
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -B evidence/managed-output-budget/verify_default_compatibility.py
```

The one actual cohost metadata observation is archived, not automatically
reproduced. No original job, frozen source, control record, PID, clock, affinity,
private clone or old failure evidence was changed.
