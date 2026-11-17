# Observer delivery test-only stdio correction

Base: `90b97cc4be642cc7bda884c11b17db700ad0a4b0`, in the independent
`/workspace/uta-observer-delivery-review` worktree. This change does not modify
runtime tools, source qualification, financial/long-run gates, active ce, source
763 or the live six-hour job. No service or live observer sample was started.

The original root discovery log is retained byte-for-byte as
`root-initial-red.txt`: 37 tests, one failure in the positive prepare fixture.
Its SHA-256 is
`d8dab1b61ab974c5d98dbc79aa0074134785078be7345b1d9e2417c291997eb7`.
`before.json` pins the original base and relevant source/test hashes.

Independent reproduction on the unmodified source isolated the cause:

| Targeted fixture environment | Exit/result |
| --- | --- |
| Actual stdout/stderr redirected to a regular log | 1 / FAIL |
| Actual stdout/stderr captured through PIPEs | 0 / PASS |

Both used `-W error::ResourceWarning` and one allowed CPU. The fixture replaced
Python `sys.stdout` with `StringIO`, but that does not replace the underlying OS
fd1/fd2. `smoke.main()` correctly rejected the unittest runner's regular-file
standard descriptors before the fixture reached the plan-only path. This was a
test assumption, not drift in the merged source qualification fingerprint.

The positive unit fixture now explicitly mocks the safe-descriptor precondition
while testing its actual purpose: prepare creates neither a job nor a producer.
The runtime guard is unchanged. A new separate negative test executes the real
smoke CLI with writable regular stdout and verifies silent exit 1 and unchanged
original file bytes. Existing descriptor safety tests remain intact.

After the test-only change, the same discovery pattern with actual regular-log
stdout/stderr and `ResourceWarning` as an error ran **38 tests in 1.396 seconds,
OK**. `after.json` records the exact command and unchanged hashes for the four
relevant runtime tools. This is micro-test evidence, not release or six-hour
qualification. Other suites reported by root were not rerun or relabeled here.

The allowlisted logs and before/after metadata are hashed in `manifest.json`.
The live job, its original control/observer outputs, all timing and the frozen
active source trees were never accessed by this investigation.
