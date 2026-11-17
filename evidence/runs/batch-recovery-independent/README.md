# Independent recovery evidence

Implementation base: `6730f444106bb816ef0d97596030ed3de1b45559`.
Clean test commit: `b008da287464d64deb9736f64b0a9a3d1b676c6b`.

`matrix.json` records the three real one-CPU Python/SQLite runs, original
commands, source hashes, raw log hashes and clean/unchanged flags. Each executes
only seven independent recovery tests; it is not a release qualification report.
`run_matrix.py` is the exact external driver, preserving its original worktree
path. `copies.json` verifies all original copied bytes.

`first-python312.txt` and `preliminary.json` are an earlier exploratory passing
run, before exact closed-owner map equality was added. They are explicitly
separate from the clean-commit matrix. `original-three-repayments-python312.txt`
retains the unchanged pre-seal-loan repayment assertions on integrated source.

No runtime edits, long job, throughput test or production approval occurred.
