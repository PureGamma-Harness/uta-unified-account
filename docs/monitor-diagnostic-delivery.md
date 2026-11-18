# Bounded parent-failure diagnostics

This changes test diagnostics only. The original stopped-owner publication
test keeps its4s publication,5s assertion,0.6s lease, successful body and
cleanup. On failure it observes two already-known parent thread roles with
at most8 frames each, writes at most32KiB once to an existing regular FD,
then re-raises the original exception. It does not query SQL, acquire the
router mutex, read worker caches, inspect a PID or send a signal.

Blocking pipes/TTY sinks and quota excess reject output; short writes are
not retried. Regular-file I/O can still block, so this is not a hard latency
guarantee. Frame metadata excludes locals and arbitrary object payloads.
The existing primary diagnostic reads bounded module-name metadata; neither
an unlocked role reference nor a stack snapshot proves ownership or cause.

Independent CODE5d644428 and ENTRYf23f5de8 precede the unique diagnostic4 run
at07f75208. Four actual method IDs passed with0 failures/errors/skips, prefix
exit0/wait/reap/bothEOF and root external actual exit0. Root independently
checked8 retained inputs58802B and the expected Python binary. The code-origin
label006b30a8 is distinct from actual execution HEAD07f75208.

Independent RAWe41b1ae9 checked10 originals24546B plus the separate seal and
8 finite SAFE exports. Raw3174B,14 recorded writes, duplicated summary418B
and512B reserve stay below32KiB. Prefix223252396ns and tool wall0.128736191s
have distinct unaligned observation scopes and are not performance evidence.
The four tests use fake frames, unstarted Thread objects and patched FD
operations; they do not execute the native recovery case or explain a CI failure.

The original wider66-input manifest is Git closure; the pure checkout had
only2 of those paths materialized. No full66 physical/native attestation is
claimed. Its actual8 pure inputs remain byte-identical after this delivery
merges current PR49 evidence. All61 UTA modules and CI/build files are unchanged.

The collection history includes an administrative missing-sparse-file check
followed by a commit despite that check failure. The exact two owned paths
were restored and rechecked; the original commit and manifest remain, with a
separate correction. This was not a target rerun. The earlier independent
CODE review also records a separate main-worktree index command with unknown
prior staging; current clean status cannot establish the missing prior state.

Deploy by running the fixed pure entry or normal tests on new synthetic
fixtures. No account schema, policy, product or API changes. Rollback removes
the test hook/helper/control files while retaining first raw observations.
Actual native recovery, registry contention A/B, current CI root causes,
blocked-I/O bounds, production and capacity approval remain OPEN/NO_GO.
First normal CI for this public test-only delivery is pending.
