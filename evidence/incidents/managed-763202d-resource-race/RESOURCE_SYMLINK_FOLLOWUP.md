# Required-main symlink review closure candidate

Independent review `2a977869620e620dac7a0d5980a37cb029183334` found that f5232c1's
single `Path.stat()` followed a direct required-main symlink to a regular file.
That could count a replacement as the required main. Original f5232c1 and all
initial red/green evidence remain unchanged in history.

The added real-temp negative ran before this follow-up change: the regular-file
symlink did not raise, and the dangling required symlink produced the wrong
failure path. The retained log records one failure and one error. The only
production-code change is now `Path.stat(follow_symlinks=False)`. A direct or
dangling symlink at a required main is nonregular and rejected by the existing
guard, with one metadata call. Dangling nonrequired auxiliary/temp symlinks are
not followed, reopened, or counted as regular-file content. Their targets are
never created or read.

The final 13-case resource suite passes under Python 3.10/3.12/3.13 on CPU 2
with ResourceWarning fatal: 0.050/0.057/0.034 seconds, respectively. Each has
zero failures/errors/skips/expected failures/unexpected successes. The real
SQLite last-close race, main-loss, EACCES/EIO, directory-enumeration failures,
budget accounting and constructor-error-preservation tests remain included.

This is resource measurement, not full path authorization: a symlink in a
parent directory is outside this closure. Native private-path/authority role
checks remain independent. The existing `run()` final-status resampling may
raise a secondary resource error after a primary failure; that documented
fail-closed reporting limitation is unchanged. This patch does not hide either
failure or modify `run()`, clocks, budgets, faults or financial/long-run gates.
No original source/job SQL, clone or service was executed.
