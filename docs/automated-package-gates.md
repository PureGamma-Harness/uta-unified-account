# Automated package gates

The four-version push and pull-request CI now builds both the wheel and source
distribution, then calls the frozen-source archive verifier with the actual
checkout `GITHUB_SHA`. A pull-request merge commit keeps that identity; it is
not relabelled as the head commit. The verifier requires every tracked source
and evidence file in the sdist with exact bytes, both runtime maps, the pinned
legacy fixture, entry points and the single source-derived version header.
Build products remain ignored outputs; unexpected untracked source still fails.

The fresh virtual environment then runs the existing installed-release checker
with `python -I` and no `PYTHONPATH`, outside the source directory. This is the
functional eight-case CLI/protocol check, including original-CID recovery and
financial receipts, plus real console commands. It does not use identity-only
mode. Source modules cannot satisfy an installed import or runtime hash check.
The ordinary demo and installed smoke steps also remain enabled.

Each matrix job preserves the archive manifest, installed report, test log and
console stdout/stderr even on failure. The artifact paths are an explicit
report allowlist: authority directories, SQLite files, credentials, TLS keys and
temporary runtime state are not uploaded. The wheel and sdist are separately
retained as review artifacts. A missing report remains missing; `always()`
preservation does not turn an earlier failed job into a pass.

This changes validation only, with no account or database migration. Rollback
is restoring the prior workflow for later runs while retaining existing failed
artifacts. Restoring it does not approve an unverified package. The first new
frozen-source CI execution must establish these gates actually ran; this
document and YAML parsing alone do not establish any package result. Local
independent installation, omitted-file counterexamples, read-view checks,
capacity, fault recovery and real-funds approval remain separate requirements.
