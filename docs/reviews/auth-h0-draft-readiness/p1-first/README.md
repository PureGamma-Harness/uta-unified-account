# P1 first actual run: four observed AuthDB ordering cases pass

Source912f2a4 / runtime5750e12; unchanged approved harness SHA `c8de834b0dcd96a1617ab5d32f593088de871923497052bde53104998b4eab90`. This is one new actual independent P1 run. It does not repeat ef60's eight fix cases, repair old authorities, rewrite the original full-suite controller records or authorize financial execution.

The detached supervisor started once at19:41:31.128267 UTC. It closed/fsynced/hashed raw files, verified source/harness stability and fsynced its result before the recorded completion clock19:41:31.874200 UTC:745,921,252ns, under30 seconds. Completion-record serialization follows that clock and is declared separately. The actual probe itself reports19:41:31.634884–19:41:31.808582,173,694,021ns before report write, Python3.12.14/SQLite3.53.1/CPU4. These are small shared-host observations, not latency/capacity qualification.

All four cases pass. Their actual schedules were:

| Case | Observed result |
| --- | --- |
| Profile/key revocation versus new capture | Profile2 revocation commits first; capture refuses401 signing_key_inactive. A separate still-current reader correctly queries AuthDB absence for that CID. |
| Unrelated profile update versus new capture | Capture succeeds under the actual profile recorded by its audit; the independent reference verifies the effective revision and a current reader query. |
| Borrow-grant revoke versus same-CID POST retry | Revocation commits first; retry refuses403. The original first acceptance remains single and byte-identical; a current reader can still query it. |
| Current read-grant revoke versus lookup | Revocation commits first; lookup refuses403. A subsequent revoked-reader query also refuses, while another independently current funding/read grant can query the original. |

This is one observed schedule per case. The reverse winner branches are not claimed dynamically covered merely because assertions exist for them. Neither exhaustive interleaving verification nor general liveness under contention is established. Intake saturation and default224+32 registry fill were not part of P1.

## Supervision and original evidence

Supervisor PID328881/birth8161757 started in a new session with stdinDEVNULL and private file streams. Probe PID328960/birth8161776 had an actual bound pidfd, exited0, and was waited/reaped by that supervisor. It is absent from `/proc` after completion. No watchdog or forced cleanup activated. Supervisor itself is observed Z/PPID1 with encoded exit0; no starter-reap or completely empty process-tree claim is invented.

The starter returned without leaving supervisor streams on the exec-server pipe. This design avoids the previously encountered stream-lifetime dependency, but no real exec-server disconnection was injected during this short run. A namespace/computer failure remains outside this observation. Existing outer directories cannot be started again automatically.

The [supervisor result](supervisor-result.json) and [completion](completion.json) bind closed raw stream and probe-result hashes; [safe start](start-record-public.json) and [actual Popen](probe-actual-Popen-public.json) preserve ownership metadata. Exact private command arguments, original streams, signed requests, profiles, keys and AuthDBs stay under the retained private outer root. Public records replace only predetermined private path arguments and contain no live nonce, signature, key or DB bytes.

## Independent post-check

The [separate read-only checker](../../../../tests/auth_h0_readiness_independent/read_concurrent_results.py) imports no product. On CPU3 under a10-second bound it reads only the four finished self-created authorities through mode=ro/query_only, read-only authorization and one consistent snapshot each. This is a completed-state audit, not another concurrent test execution.

[Its result](completed-state-postcheck.json) verifies clean FKs, actual audit/profile/control sequence associations, historical accepted-payload false authorization flags and immutable identity hashes. It recomputes11 exact retained private request MACs literally; no secret/request value is exported. Signed requests that fail authorization are not claimed to have produced accepted records or consumed a nonce beyond their actual policy. All original source/runtime and harness hashes remain unchanged.

The [scope verdict](scope-verdict.json) accepts only these four source-bound observed ordering cases. Whole H0, full legacy compatibility, all concurrency schedules, package/CI/install, default capacities, true process reply-loss, H1–H4, HA, anti-rollback, financial execution and production remain unaccepted. The original full3 inner PASS summaries and missing outer records retain their separate incomplete-controller verdict; P1 does not change those files.

No deployment or migration was performed. Preserve accepted identities and tombstones and all original failed/UNKNOWN records. Any next experiment requires a separate root decision and a fresh private namespace, not a restart or rewrite of this first run.
