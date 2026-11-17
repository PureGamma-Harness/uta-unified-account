# Independent package acceptance: 13e6924

Frozen source: `13e6924377f031bb3da7ec94aa88df25ed7612ec` at
`/workspace/uta-operations-freeze-13e6924`, kept unchanged and clean.
Report worktree: `/workspace/uta-package-13e6924`.
Fresh external build/install: `/tmp/uta-release-13e6924-yHMFC2`.

The new artifacts pass the independent package checks. All **1171 tracked
files at the frozen commit** occur in the sdist with exact bytes, including the
diagnostic logs, JSONL and compressed JSON added to the manifest. Both artifacts
contain exactly the frozen **49 runtime files**. The runtime tree SHA-256 is
`5ff942d526d904fd74e1843f29e955ca923a223a425d88cb08bfa436f5c6f36b`.

This runtime differs from `7200097`: `uta/startup.py` and `uta/durable_views.py`
are added, and ten existing runtime files change. `runtime-delta-from-7200097.json`
records that byte comparison. Earlier functional passes are not reused. New
installed module records identify both added modules inside the fresh venv.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `uta_reference_exchange-0.4.0a1-py3-none-any.whl` | 257034 | `8a89f68cc201cf07b3e599e020dd38e9cb565353fc10b561e7f66f86415d52a7` |
| `uta_reference_exchange-0.4.0a1.tar.gz` | 21326149 | `e97557d711ae0b9cf3f17edc68430c539566ad96d0190341b4d5ef90b3b832d6` |

The wheel is built from `git archive` in a directory without `.git`, then
installed with `--no-deps --no-index` into a new external venv. The frozen
installed verifier runs under `python -I` with `PYTHONPATH` unset. All **eight
actual installed CLI/protocol tests pass in 9.161s**, with no failures, errors
or skips. All eight console commands also exit zero: durable help/init/inspect/
status, ops help, demo, functional acceptance and scenario. These tests exercise
the new worker startup code with real child processes, SQLite, verified TLS and
HMAC on synthetic data. Small fixtures do not establish long-history startup
scaling or a six-hour recovery qualification.

An additional installed smoke uses three **unchanged frozen read-view tests**:
all account resources with exact stored values and no financial constructor on
the read path; HMAC reader/account scope; and actual HTTP reads selecting the
correct one of two managed shards. The final run passes **3/3 in 0.658s** with
zero skips. The copied helper's SHA is pinned to the frozen Git bytes, and every
loaded `uta` module resolves inside the installed venv. The original tests use
constructor-raising tripwires during reads; synthetic financial setup still
writes fixtures. The HMAC view case uses localhost **HTTP**, with
`require_tls=False`, and writes the separate authentication nonce database.
Financial read-phase snapshots remain unchanged. TLS lifecycle is tested by
the separate CLI suite; the three view tests do not claim TLS coverage.

The first new view harness selected the router method from the wrong test
class. It failed during suite construction before running any test or financial
fixture. The exact initial harness and raw error are retained. Correcting only
the class mapping produced a successful three-case run; after a docstring
clarification the final committed verifier was exercised again in a new output
directory. Both successful logs and the original zero-test failure are retained.
No frozen helper or runtime implementation was changed to obtain a pass.

The sdist was unpacked into a fresh directory without `.git`. All seven real
legacy-writer fixture tests, the one archived managed-probe/profile test and
four archive-verifier tests pass, with no skips. The profile test preserves the
historical probe's limits and failure; it is not a new load result. Build and
functional test processes are pinned to one available CPU. No benchmark or
six-hour run is started by this package exercise.

Two actual negative controls independently copy the new artifacts and omit
`uta/startup.py` from the wheel or `uta/durable_views.py` from the sdist. The
primary dynamic archive gate exits 1 in each case and reports the expected
runtime mismatch; the sdist also reports precisely its missing tracked view
module. These deliberately incomplete artifacts are never installed. Their
hashes, exact argv/cwd, reports and raw stdout/stderr are retained.

`artifact-manifest.json`, both installed reports, `package-verdict.json`, source/
verifier hashes and all raw logs bind this result to the exact frozen source.
`commands.txt` contains the repeatable commands, and the additional view harness
is retained as `validate_installed_views.py`. These report files are created
after the frozen build and are not claimed to be members of that sdist. Earlier
package artifacts and all original red evidence remain unchanged.

This is local Python 3.12 package acceptance. The integration gate owns the
separate 1078-test runtime matrix. No old long-run result is reassigned to this
source; no six-hour run, systemd deployment, public listener, sustained capacity,
HA, custody or real-funds qualification is established here. Production scope
and approvals remain unchanged: `production_approved=false`. Artifact binaries
stay in the external artifact directory. Authority/auth databases, TLS private
keys and signing profiles are not committed.
