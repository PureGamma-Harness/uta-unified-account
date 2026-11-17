# Ledger guard damage: original red evidence

Baseline: `5d0f34acba48e59f59650013b190edf8a72faa8e`.
Review worktree: `/workspace/uta-ledger-guard-review`.

The single actual test exits 1 because the current ledger verifier accepts a
same-name/same-table posting UPDATE trigger with `WHEN 0`. Its actual output
also records reopening and public managed take-over accepting that guard,
while the one synthetic double-entry post and all prior source rows remain
unchanged. No worker is started. The real temporary posting UPDATE is observed
and rolled back before inspection; only the schema guard fault is retained.

The fault requires the trusted local database owner to deliberately replace
schema SQL offline. It is not a customer API operation, a custody claim, or a
proof that managed lease guards can be bypassed. The fixture uses synthetic
10 USD funding and leaves no authority database committed.

`original-red.stdout.txt` and `original-red.stderr.txt` are unmodified raw logs.
`observation.json` is parsed directly from the raw stdout's
`ledger-guard-evidence` line. `manifest.json` binds the baseline runtime, added
test, documentation and evidence. The intended rejection assertions remain red;
no runtime fix or green rerun is included in this review commit.

See `commands.txt` to reproduce the same one-CPU case in a disposable temporary
directory. The full static trace and boundaries are documented in
`docs/ledger-guard-integrity-review.md`.
