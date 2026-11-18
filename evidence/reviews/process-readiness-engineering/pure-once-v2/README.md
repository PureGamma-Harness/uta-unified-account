# First pure reference result

The sole authorized batch on frozen source
`cb35a277d3f77c1bcb9ef9ab7efae398beae2c4f` passed: **7 methods, zero
failures/errors/skipped, exit0**. It used Python3.12.14, one CPU affinity,
and a10s wall budget. Unittest reported0.018s; the runner reported0.209s
including its imports, source verification and setup.

[Intent](intent.json), [complete first stdout](stdout.txt),
[complete first stderr](stderr.txt), [exit status](exit-status.txt), and
[source pins and derived result](result.json) are retained. No run was retried.
All nine declared source pins matched before and after. This is the declared
fixture/runtime source map, not every repository file or runtime dependency.

The seven pure methods cover quote creation after an owner witness; preservation
of a first unknown with no second diagnostic; strict identity integer types;
fake-clock native-return completion exactly at or past the total deadline;
PID/generation/lease mismatch; unmatched consumed READY; and late top/shard
timeout or guard failure even after owner fields were populated. The actual
native clock was not patched. Source-only candidate `2d12a2e` was never run.

The batch prohibited UTA/SQLite imports and recorded none. It started no actual
router, worker or service and performed no SQL, signal or network action. These
synthetic cases prove fixture behavior only. The two original PR34 CI failures
remain separate and unresolved; this PASS does not replace them or establish
their causes. An actual native case still needs a separate small plan,
resource preflight, frozen driver, first raw journal and scope authorization.
