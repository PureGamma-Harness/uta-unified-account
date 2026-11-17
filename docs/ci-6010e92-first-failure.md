# PR25 source6010e9: original push Py311 failure

Overall qualification remains **NO_GO**. Source `6010e920a168b35fccfc9ef9ee34e030b28b11d9` has a first-attempt push failure which the successful PR run does not supersede. This seal preserves original evidence and locates the failing assertion and adjacent sanitized thread observation; it does not determine the root cause, change tests/timeouts, rerun CI or start the pending local313 qualification.

| Original scope | Actual result |
|---|---|
| Push run44184136107, attempt1 | Py311 job134395997553 FAILURE; other3 jobs SUCCESS |
| PR run44184574093, attempt1 | All4 jobs SUCCESS |
| Failed push311 unit artifact14373841721 |94548B; SHA256 `c208946e8a83b4b4bf1e0297e8a9cb244a193992f16566dd079d0a8bbe1430c2`; CRC PASS |
| Comparison PR311 unit artifact14374011525 |92813B; SHA256 `cf7894be5f1d811861c4dfa3677bdd1233920cb74f33e8599578f05875378762`; CRC PASS |

GitHub jobs/whole-step and artifact metadata were each read once per run using the plugin. Run-attempt/timestamp and Git parent/tree fields, absent from the plugin's reduced projections, were obtained from read-only GitHub API fields. The original decoded failed-job log is25817B, SHA256 `162e10ca3ecc8c8310882ed3071e2d2e63f1977b3ad8d367202521cf0e2f4778`. The full log and both original ZIPs remain under0700 `/workspace/uta-ci-6010e92-first-failure-private`; raw log/ZIP files are0600. No signed download URL, authentication material or binary ZIP is committed.

## Exact first failure

The original push311 report says **1830 tests,1 FAIL,0 ERROR,0 skipped,0 expected failures,0 unexpected successes**. The failing test is:

```text
test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover
(test_durable_faults.ManagedProcessFaultTests)
tests/test_durable_faults.py:1456
AssertionError: bound child did not leave SH after undo within original capture horizon
```

This is an assertion failure, not an ERROR count. The unit wrapper reports296.28222859s; raw unittest reports1830 tests in294.792s. Unit worker exit1, passed=false; source unchanged/clean before and after are true. The unit step fails and the complete-unit-evidence upload succeeds. Compile/demo/replay/formal/build/install steps7–20 and wheel retention22 are skipped; package-evidence step21 executes successfully as configured but produces no package artifact for failed311. It must not be described as a passed package/install validation.

The full original push `worker-result.json`, `summary.json` and371063B `unittest.txt` are preserved unchanged. The comparison PR311 original summary/worker are preserved separately; its original full unittest remains inside its private original ZIP. Public raw output contains synthetic repository tests and the source's sanitized diagnostic. A bounded pattern check found no URL or credential-value assignment in this unit text; this is a publication check, not a general security audit.

## Actual neighboring diagnostic and evidence gaps

The first quick scan looked for faulthandler `Thread 0x`/`Current thread`/`Timeout` markers and found none. That search was insufficient: unittest line483 contains **one** `UTA_EXPIRED_GATE_FAILURE_DIAGNOSTIC` JSON record from source6010. This correction was immediately sent to root and the connection-lifecycle author. The exact original JSON substring is preserved; no reserialization is substituted for it.

At `before_original_cleanup`, the record contains one capture attempt and one injection undo. Its last capture retained one selected binding after the stop, but `writer_availability_probe` is `available=false`, `native_errorcode=15`. The selected synthetic binding is PID2657/start_ticks16550/uid1001. The original fixture lease/capture/recovery/API horizons remain5s and publication lifecycle watchdog15s.

The monitor is observed alive, with monitor_stop=false. Its sanitized frames include `uta.writer_fence._load:179`, `uta.storage:210`, `storage.read_transaction:165`, `uta.sharding.read_transaction:97`, `writer_fence.status:519` and `uta.durable_process._supervise:1337`. The main-thread frames include diagnostic generation and test cleanup observation at test line1587; the primary exception points to1456. The publisher record has **alive=null, frames=[]**, and publisher_errors=[]; this is unknown status, not proof of absence, startup, health or success. Ten fields were intentionally dropped by the diagnostic's privacy projection. No native child stack, complete lock history, or causal interpretation of numeric error15 is supplied here. The test observed failure to leave SH within the original horizon; this evidence alone does not establish why.

## Source, build and actual PR merge

Push artifact code_commit is the exact source6010. Original PR311 artifact code_commit is **`98d161640972627c3c39e55baf92a2eaf1406b59`**, the actual PR merge, not the run metadata's head SHA. Provider Git metadata gives parents `[e4396b4b1fd9c2e3a138e48a045feffe158705cc,6010e920a168b35fccfc9ef9ee34e030b28b11d9]`. Both source and merge trees are **`98b8d00850c24864e1c2026e7a9749140866b7bd`**. Their353-input SHA256 maps are identical before/after, and every input was independently checked against source Git blobs. Source has6274 tracked entries; the61-file `uta/*.py` runtime tree is byte-identical by Git blob identities to core **`ff814d4bcaee079b0e0503ea8072c24e3563c443`**.

The failed job's actual runtime log record says Python3.11.18, GCC15.2.0, SQLite3.46.1 with59 compile options, Linux7.0.0-1019-azure/glibc2.43,4 CPUs/affinity0–3, cgroup_cpu_max=null. The4147B original timestamped runtime excerpt is preserved, plus an explicitly reserialized JSON projection of that same record. No hardware/replication/capacity qualification follows from this runtime metadata. PR311's actual1830/0FAIL/0ERROR PASS remains a separate result, not a replacement for the first push failure.

Provider metadata lists **22 actual artifacts**: push10 (four unit, three package, three wheel), PR12 (four of each). This urgent seal downloads and verifies **only the two original Py311 unit ZIPs**. It does not claim the other20 binary archives, seven wheels/sdists, or all eight unit summaries have been downloaded or independently qualified. Their actual provider IDs/digests/byte counts and all eight jobs' complete step summaries are preserved for subsequent collection without another run.

## Read-only acceptance and reproduction

Independent first reader: `2026-11-17T22:21:54.422042+00:00` to `22:21:55.248781+00:00`, CPU3/15s watchdog,826743380ns, exit0. It checks original ZIP digests/CRC/member bytes, both source identities/counts,353 Git inputs,61-file core equivalence, the exact diagnostic JSON substring, provider parent/tree/step facts, and failure preservation. Source/hash/stdout/stderr are retained.

```sh
taskset -c 3 timeout 15s python -B evidence/ci-6010e92-first-failure/read_original_evidence.py \
  --private /workspace/uta-ci-6010e92-first-failure-private
```

Verdict: **PASS_READ_ONLY_FIRST_FAILURE_EVIDENCE** with system qualification **NO_GO**. The actual failing test and sanitized diagnostic were delivered to the connection-lifecycle author before this commit. Zero SQL, financial/native runtime, QA reruns, CI reruns, timeout changes or pending-local313 starts occurred. Any diagnosis or fix needs a distinct source and review; this evidence does not authorize another execution.
