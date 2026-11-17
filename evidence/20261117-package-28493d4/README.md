# Intermediate release candidate 28493d4

The frozen source was `28493d4f1ca78b8452a1e337e2cd5277a81d95a5` at
`/workspace/uta-durable-final-28493d4`. Its fresh wheel passed all eight actual
installed CLI/protocol tests in 7.961 seconds, with no failures, errors or skips,
and all recorded installed console commands exited zero. The runtime contains
the same 47 files and tree digest as the earlier `89bd349` wheel. These results
apply to this intermediate source/artifact pair.

**The package gate is failed.** The original archive verifier reported success
because its required-file set covered only part of the tracked source. A second
complete inventory of all 796 tracked paths found four source-distribution
omissions: `.github/workflows/ci.yml`, `.gitignore`, the archived
`benchmarks/results/20261114-wal-lifetime/regression.txt.gz`, and
`evidence/runs/sqlite-fixture-resourcewarning/allocation-probe.py`. The original
green report is retained as `initial-artifact-manifest.json`; the strengthened
verifier's actual exit-1 report is `artifact-manifest-complete.json`.
`package-verdict.json` records the complete package result as false.

The actual-release negative control copies this source distribution and adds
exactly the other three omitted files. The allocation probe is still absent.
The strengthened verifier exits 1 and reports exactly that missing probe. This
control is a deliberately modified test artifact, not a repaired release. Its
construction, actual argv, observed return code and complete verifier output
are retained. Four automated verifier tests also pass, covering healthy source,
required-file omissions, duplicate ZIP/tar members, extra runtime files, changed
documentation bytes and a dirty tracked source.

The proposed manifest adds the missing formats and two explicit repository
configuration files. Setuptools `egg_info` in a separate frozen-source copy
with only that revised manifest selects all 796 tracked files. It builds no
wheel or source distribution. An earlier bare `FileList` inspection omitted
setuptools' automatically selected Python/package inputs; its failed helper
assertion is retained in `manifest-selection-complete.*`. The full `egg_info`
selection is recorded in `revised-source-selection.*` and is the supported
static check. A new frozen source and real build are required to validate the
repair.

The installed acceptance verifier additionally closes both direct read-only
SQLite connections with `closing(connection), connection`, preserving their
transaction context semantics. No `uta` runtime source is changed here. This
follow-up has not built a new artifact or claimed new installed results.

Artifact binaries remain in
`/tmp/uta-release-final-20261117-0ibLCN/artifacts`; their exact hashes and sizes
are in the retained manifests. No authority database, signing profile or TLS
private key is committed. No production, HA, 10,000/s, long-duration, custody or
real-funds qualification is established.
