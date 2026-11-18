# Independent cold-import parent review: 87c9675

The new final parent guard passes the authorized narrow CODE/PURE review. This is test infrastructure qualification for the stated trusted-source import contract. It does not close any original CI, native-SH, filesystem, financial, capacity, HA or production gate, and it grants no M05 execution permission.

Fixed source is `87c9675d9852d709782d7f461661c66f2e0ba80d`. The actual helper is `tools/cold_import_contract.py`, SHA256 `91c4a813e4147bcdfb68cc28b3d0f0604e9ec5c6f0a94dac28f23972675223c5`. Immutable source bindings, first outputs and the independent script are in `evidence/reviews/cold-import-87c-independent/`.

## One independent pure-stub batch

At `2026-11-18T00:20:31.384381+00:00` to `00:20:31.579230+00:00`, one CPU3 batch with an external 10-second limit completed in **194,862,337 ns**, exit 0. Six stub cases passed:

- A primary wait OSError followed by a cleanup wait returning zero retains `UNKNOWN / CHILD_OS_ERROR`, with no accepted proof.
- Timeout followed by cleanup zero retains `UNKNOWN / CHILD_TIMEOUT`.
- Failure to reap retains `UNKNOWN / CHILD_REAP_UNKNOWN` with `child_reaped=false`.
- Extra JSON fields, duplicate JSON keys and non-JSON output each retain `UNKNOWN / CHILD_PROOF_INVALID`.

The first two fakes emit an otherwise valid, source-hash-matched proof before the wait fails. The final guard requires `CHILD_EXITED`, so neither can gain PASS from the cleanup return code. Only fake Popen/wait/kill objects run; they create no actual child, SQL connection, crypto process, network activity or signal. Audit events and imported SQL/UTA modules are empty. Synthetic private sentinel contents do not appear in the public result; closed output sizes/hashes are retained. Three malformed variants supplement the four requested parent error classes; no original eight-case or four-real-child batch is repeated.

First stdout is 4,630 bytes, SHA256 `f078ae1715bb1c4c47dbd9fa1beda698f7b9678f5e858790335db3bbd051cc78`; stderr is empty. The checker SHA256 is `5ca6bcce2f953b8e930732dd8a98fe4aa02b89907619765ee00f1638aee8c968`.

## Separate first and final source identities

The author's original eight-method batch used helper SHA256 `371fffa8397ccba2734d5b71a5c481ce0ae8dcb1611723e3bc794695b568ee72`. Its original source snapshot and raw results remain unchanged. The single final helper difference is `if result['code']=='CHILD_TIMEOUT':return result` becoming `if result['code']!='CHILD_EXITED':return result`. The final ninth test was not part of that author eight-method run. This independent six-case parent batch supplies evidence for the final guard without relabelling the first run as final nine-method acceptance.

The child program is byte identical before and after that guard, SHA256 `45eb3b18b0e5e36deefefbf1698d1b4402d649909d0f6cd75e2423590018e931`. The four original child safe JSON records were read and hashed only. They bind the old controller `8cc1116d...` and escrow `89f48b50...`, two canonical import negative controls, isolation/no-site flags and zero blocked cache. They do not qualify the later filesystem-token candidate or all CI runtimes.

## CODE scope and remaining boundaries

The child installs import guards before reading/executing the trusted target; canonical sqlite3, _sqlite3 and uta roots are rejected. Fresh `-I -S` interpreters and filtered PYTHON* environment isolate legitimate parent module caches. Strict parent JSON checks bind mode, target SHA, flags, version and guard events; raw exceptions are not copied to results. Both workflow diffs contain exactly the new helper/test sparse paths and keep the existing discovery pattern. Controller/escrow bytes, source909 financial workload arguments, policy namespace, budgets and the runtime `uta` Git tree are unchanged by this commit.

This is not an arbitrary-code sandbox, import alias/dlopen or preloaded library defense, nor a proof about future function calls. Parent kill/reap is limited to the directly owned child; blocking kernel calls have no physical real-time guarantee. No actual interpreter/process was run by this reviewer, so the author's original four child executions remain the sole real-import evidence for their fixed target bytes. Original general CI and native-SH failures remain NO_GO until separately verified under a new immutable source identity.

This OWN adds documentation and synthetic review evidence only. Reverting it has no account/schema migration or service effect. Reverting the helper separately restores the known fragile process-wide module-cache assertion; rollback must keep all first failure/raw artifacts. Parent integration and any future real test execution require their own explicit scope.
