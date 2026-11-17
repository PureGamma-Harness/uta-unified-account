# Independent startup-phase review of ed1f141

Reviewed exact commit `ed1f1414b3f28aa1ff41b4d7e74b12b565a32c3f` in the separate
worktree `/workspace/uta-ci-a35-startup-review`, branch
`review/ci-a35-startup-phase`. No new blocker was found in this test-only patch.
An independent read-only peer (`future_checkpoint_anchor`) reached the same
static conclusion. This review did not edit the subject tests or runtime code.

The only changed source input relative to
`a35fd56fc98126b3e5cced8a459bd04ca580e537` is
`tests/test_owned_startup_reference.py`. Its only changed method is the positive
old-inflight-writer test; the other 12 reference tests, all four contention
tests, and every runtime file are unchanged. The top-level docstring now calls
`d9afd46` the test's origin rather than asserting that the present source is
that immutable commit.

The five-second lease applies only to this positive test. It matches the
existing production defaults in `uta/durable_process.py` and
`uta/durable_cli.py`; the fixture's default and all negative cases remain
unchanged. The keeper's actual timeout remains
`min(database.timeout, lease_seconds / 12, .1)`.

`completed.set()` occurs after leaving the original `bound.transaction()`:
normal completion includes its real final guard, COMMIT and connection close.
The Event alone also permits an exception/rollback, so it is not independently
a successful-COMMIT claim. The test additionally requires an empty failures
list, a terminated writer thread, exactly one visible `old-inflight` journal,
and the original complete `DurableLedger.verify()`. The renewal wrapper releases
the writer, waits for completion, then calls the original native renewal.
No keeper result, lease clock, private verifier flag or financial result is
manufactured.

Release, completion and final thread-join witnesses each remain bounded at one
second; startup's three-second deadline is unchanged. These are individual
witness/deadline bounds, not a proof that the whole test has a three-second
wall-clock upper bound. The changed positive case proves the coordinated
ordering, not success under every old-writer contention schedule. Severe
scheduling delays can still fail closed. The separate uncoordinated producer
test retains a genuine inbox writer lock, original renewal, five-second lease
from first acquire, actual `.1` busy timeout, native `OperationalError` locked
cause, `startup_keeper_failed`, and `_finished == False` assertions.

The two requested modules were run sequentially on CPU 2 under Python 3.10.22,
3.12.14 and 3.13.5 with `-W error::ResourceWarning`. Each ran 17 tests with zero
failures, errors, skips, expected failures or unexpected successes. Worker
affinity was actually `[2]` for all three. Suite times were 6.057875, 5.935585
and 5.962016 seconds; total measured execution was 18.520057 seconds, from
2026-11-17T10:58:14.452517Z to 10:58:32.972566Z. The runner imposed a shared
55-second child budget, below the authorized 60-second ceiling. Before/after
source inventories are identical. All raw output, worker records, exact argv,
runtime/SQLite versions and source hashes are retained here.

Actual command, executed in this review worktree:

```sh
python3 -B evidence/reviews/a35-startup-phase-independent/run-focused.py
```

The runner uses exclusive new log files so that this invocation cannot silently
overwrite the retained evidence. No long service, load test, live-job sampling,
SQL probe against existing jobs, or CI/full-validation run was performed.

The original red CI remains red: 1243 tests, zero failures and one error.
Independent git-object hashing matched all 227 original recorded source inputs
to `a35fd56`; original before/after inventories also match. The existing ZIP at
the root author's target worktree is present (52,713 bytes; SHA-256
`eb858fb3f0b0daf45040f4f9f784c93ac22acf9355cac5806155861a02b1bd4b`). Its
three members match the committed original summary, worker record and raw
unittest log byte-for-byte. It is referenced rather than recopied here; its
ignored/untracked status in the author's worktree is not evidence of loss.
The retained controlled before/after comparison is a representative true
0.2-second call-through pause, not proof of a unique historical CI scheduling
cause; this review checked its files and hashes without rerunning it.

This focused PASS does not convert the old failed CI into a pass and does not
qualify a combined release, production, performance capacity or any long run.
New combined-source qualification remains separate. The active ce observer
tree, producer 763 source, live six-hour job, and original old jobs were not
opened, modified, signalled, restarted or resampled by this review.
