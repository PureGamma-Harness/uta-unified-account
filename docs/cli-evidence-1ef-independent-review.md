# Independent CLI evidence review: first identity-boundary findings

Fixed test-only candidate **`1ef63c8eb994eeb3e6b83ba730f31fc9421278d0`**, helper SHA256 `833aa7706ad9a3c3aa4afc7370206bc2af530011eb65b6579a5f05fc45c97943`, is **NO_GO pending identity normalization and reliable cleanup registration**. The one independent fake batch produced **3 RED /5 PASS**. These are injected-reader contract findings, not an observed leak from the default `/proc` reader or a cause for the original CLI shutdown ERROR.

## Original business contract and retained first ERROR

The base is exact **`6b7d473c0fbf92b17c146140c88eb2c25d38dce1`**. Independent normalized-method AST matches the base, SHA256 `a5884f2d24313698722277f803206c460aa1ef7e2a38055dfdae7820df01d128`: original argv/environment/policy/startup5s/health3s/SIGTERM/exit5s/financial assertions remain. The only deliberate PIPE observation difference is binary stdout/stderr and bufsize0; this may change scheduling and cannot reproduce an old run's missing bytes. The original cleanup5s semantics are replaced only to retain their result. The uta Git tree is unchanged.

Public old evidence9951e84 records actual Python **3.13.5 (GCC14.2.0), SQLite3.46.1**, source6b7,1813 tests/0FAIL/1ERROR, not a new helper result. Its exact CLI wait-timeout cause remains unlocated. No child stack, raw PIPE stream or timing is retroactively reconstructed, and unrelated SH CI observations are not substituted.

## Single independent fake batch

CPU3/10s, `2026-11-17T23:34:56.507024+00:00` to `23:34:56.645176+00:00`,138158305ns, exit1. Complete source/stdout/stderr/hash metadata is retained in `evidence/reviews/cli-evidence-1ef-independent/`. It creates only owned tiny private artifacts and uses fake processes, identities and clocks; no real Popen, SQL, CLI, worker, signal, H1 AuthDB or child bootstrap is invoked. The author's seven tests were not rerun.

Five controls pass: exact binary prefix plus >41KiB stdout suffix without loss/repetition; timeout retains prefix plus partial buffers but stays UNKNOWN/incomplete/unreaped; cleanup OSError remains UNKNOWN and preserves the identical original primary; archive OSError preserves that primary and reports archive_retained=false without emitting its message; confirmed success creates neither archive directory nor notice. Saved files/directories are0600/0700. A second cleanup does not overwrite first bytes.

Three fake identity-reader boundaries fail:

| Input boundary | Actual1ef behavior | Required contract |
|---|---|---|
| observed=true with only pid |Missing birth/boot/UID become None on both sides, so same_child_birth=true |Incomplete identity is unknown and cannot confirm same birth |
| Valid identity plus synthetic nonce/path extras |Unfiltered dictionary is embedded in the public notice |Strict typed allowlist; no raw extra data copied |
| Reader returns None |Constructor raises AttributeError while building first event |Invalid observation becomes safe unknown; optional observer must not leave cleanup unregistered |

`_observe` currently catches reader exceptions but passes returned objects through unchanged. Shape/type normalization is absent. In the actual test, CliFailureEvidence is constructed **after Popen and before addCleanup**, so an observer-construction failure also has a cleanup-registration gap. These controls do not prove the normal default reader supplies malformed/extra data. They establish the injectable observation boundary's behavior and the lack of fail-closed identity/privacy validation, rather than claiming a default real credential disclosure or a new authority grant. Identity observations do not authorize new signals.

The fix should normalize allowed fields and exact types, require complete PID/start/boot/UID binding before observed/same-child claims, safely reduce malformed/throwing readers to unknown, omit all raw extras, and arrange original owned cleanup before optional evidence construction. Preserve the original exact primary and existing binary/5s/business semantics. The first3RED/5PASS source and outputs must remain unchanged; later results need a distinct source pin.

## Concrete next single-case native driver — BLOCKED, NOT EXECUTED

`bounded-driver-proposal.json` names the exact original case and old-runtime target. Execution remains false until the identity findings close, independent review finishes, root freshly admits protected jobs/storage/runtime and gives explicit GO for a concrete frozen source/driver. Use one selected unittest name, not discover/full QA or a natural retry loop; the candidate has not earned execution from its fake results.

The suggested independent owned-session supervisor bounds the whole test at55s, then TERM2/KILL2 with bound PID/birth/session/descendant cleanup, protected-process exclusion and UNKNOWN if cleanup cannot be proved. These limits do not extend the inner5s selector/exit/communicate or3s health checks, nor prove a hard interruption of a blocking readline/native/join/close. Preserve actual CLI argv unchanged; no faulthandler/bootstrap, extra CLI signal, altered runtime entry or H1 probe is added. Root must supply the matching actual3.13.5/3.46.1 interpreter identity; no automatic install/substitution is implied.

Set a new private0700 TMPDIR outside source before interpreter startup so both original fresh synthetic test files and failure archives remain within the separately admitted owned footprint. Never point at existing H1/authority/credential data. Keep full first raw streams/argv only privately with file hashes; public output is strictly typed phase/identity/completeness/type/size/hash metadata. Record every unknown/no-EOF/reap failure rather than upgrading it to complete. Keep original9951 evidence and every new first result; no retry-to-green or production/HA/capacity claim follows.

Rollback is a test-only revert while preserving all first artifacts. This review does not resolve graceful CLI shutdown, authorize real execution or modify runtime/funds/schema/timeouts.
