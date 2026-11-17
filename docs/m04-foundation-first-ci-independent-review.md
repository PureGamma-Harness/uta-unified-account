# M04 source: first general foundation CI review

**NO_GO.** General foundation CI run **44199787800**, source `e643661dbafdff76e66c50d20eecc2fdef4bf9e1`, push event, attempt 1, failed. This is a different workflow from the already preserved hosted diagnostic run **44199787770**. Their outcomes are not interchangeable.

All provider objects needed here were fetched once. Four new unit artifacts were each downloaded once and retained privately. No CI invocation was rerun or dispatched; the old source was not rebuilt, retested or modified. No SQL, owner, crypto helper, key or financial operation was accessed.

## Actual execution

| Python | Job | Unit tests | Failures | Errors / skips | Package step 19 |
|---|---|---:|---:|---:|---|
| 3.10 | 134450614318 | 1,959 | 2 | 0 / 0 | SKIPPED |
| 3.11 | 134450614340 | 1,959 | 3 | 0 / 0 | SKIPPED |
| 3.12 | 134450613641 | 1,959 | 2 | 0 / 0 | SKIPPED |
| 3.13 | 134450613896 | 1,959 | 2 | 0 / 0 | SKIPPED |

Every job failed at step 5, **Run unit tests**. The package build/verification step was skipped in every job. Therefore the actual package result for this workflow is **NOT_RUN**; no missing-files package report was produced by this run.

The [machine-readable observation](../evidence/reviews/m04-foundation-first-ci-independent-20261117/observation.json) records the job states and provider bindings. The four unit ZIPs passed provider SHA-256/size and all three member CRC checks. Each summary's unittest hash and all **357** before/after source-map entries independently match Git blobs at the actual source commit. Full raw logs, ZIPs, provider wrappers and download references remain private.

## Two common import-isolation failures

All four jobs fail:

- `test_independent_m0_escrow.EscrowContract.test_no_sql_or_product_import`
- `test_independent_m0_integrity.IntegrityClosure.test_no_workload_or_sql_import`

Both assertions report “True is not false.” Static source inspection finds the shared predicate at `tests/test_independent_m0_escrow.py:108` and `tests/test_independent_m0_integrity.py:141`: reject any `uta`, `uta.*` or `sqlite3` module anywhere in the test process's global `sys.modules`.

That predicate does not attribute an import to the tested controller/helper. Other tests in the full discovery suite legitimately load the UTA product and SQLite. A global process-state assertion therefore does not establish that these target modules violated the no-SQL/product-import constraint. An appropriate correction must preserve that constraint and test the target imports causally, for example in a fresh bounded process with import denial. Deleting the constraint or clearing shared modules is not justified.

This review did not run an extra import experiment or apply a test fix. The actual four failures and first stdout/stderr remain immutable.

## Separate Python 3.11 native failure

Python 3.11 also fails `test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover` at **line 1525**:

> original bound PID did not exit within the unchanged five-second recovery horizon

This is a third observed assertion within that natural test. Earlier saved runs failed during capture-attempt exhaustion or undoing a captured SH owner. A common test name does not establish that the assertions share a root cause. This recovery-horizon failure remains unresolved; the import-isolation correction cannot be presented as resolving it. No native reproduction or deadline change was performed here.

## Static packaging gap, distinct from actual CI

At this exact source, `MANIFEST.in` explicitly includes only `.github/workflows/ci.yml` from the workflow directory, and its config rule is `recursive-include config *.json *.md`. The following tracked public files are not explicitly selected by those rules:

- `.github/workflows/independent-m0-once.yml`
- `.github/workflows/independent-m0.yml`
- `config/m0-stream-recipient-public.pem`

The PEM has a **public certificate** header; no private key was read or proposed for packaging. Path hashes and sizes are recorded without publishing its contents. The declared build backend is setuptools, with no repository declaration of a VCS file-discovery plugin.

These facts identify a **static source-distribution selection gap**, not a package failure observed in this run. A separately reviewed manifest correction can explicitly select the required public files and receive a newly labeled build/verification. This review did not rebuild the failed source to turn the static concern into an extra test result. The archived M04 source, marker and controller remain unchanged.

## Deployment and rollback

This is an evidence/documentation-only commit. It changes no runtime, schema, service, risk rule, controller, workflow, manifest or active long test. Keep package correction, import-boundary test repair and native recovery investigation as separately reviewable changes with their own source identities and preserved first results.

Revert this report commit to withdraw the public interpretation while retaining all original artifacts and failures. No deployment or real-funds enablement is authorized. Production and capacity approval remain false.
