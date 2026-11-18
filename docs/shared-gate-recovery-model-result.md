# SPAWNED registration progress repair: first pure results

The minimal candidate removes the default ten-second SQLite busy-handler setting
from SPAWNED registry operations in the sole supervisor. It uses a private
shallow database copy with `timeout=min(original.timeout, .1)`. The original
shared database, other event kinds, single registry INSERT, registration UNKNOWN
outcome, gated-child cleanup and new-child backoff retain their behavior.

This repairs an independently demonstrated conditional progress defect. It does
not establish PR 35's unique failure cause, native latency, five-second kernel
recovery or production approval. No native test, actual SQLite connection,
worker, process signal, thread or original authority was used in either model.

## Frozen source and first executions

| Item | Immutable identity | First result |
| --- | --- | --- |
| Runtime base | `6010e920a168b35fccfc9ef9ee34e030b28b11d9` | Original runtime source |
| Base model/evidence | `e96f5af` | RED_CONDITIONAL_LIVENESS_WITNESS, 16 scenarios |
| Candidate source | `748990b` | Ten-line source diff, including removed line |
| Candidate source closure | `03af81d` | Manifest SHA256 `9b064ab96dcc6afa9f6f9a43c2046f1ae1649509edadc298e9434043fa971113` |
| Candidate first model | `evidence/shared-gate-recovery/candidate-first/` | MODELED_BOUNDARY_PASS, 24 scenarios |

The old first execution used only CPU 1 and took 0.046 real seconds in the shell
tool. Fourteen known expired matching-owner schedules exceeded the unchanged
five-second virtual recovery deadline; their selected model kill occurred at
10.05, 10.1 or 20.1 virtual seconds. The 20.1 witness includes another synchronous
registry retry before scanning the held owner again. Unknown/mismatched lease
observations authorized no model kill. The harness exited 0 because it preserved
the required RED witness; base recovery did not pass.

After the exact source closure was frozen, root and independent static review
found no new blocker in this small diff. The one separately authorized candidate
execution used only CPU 1 and took 0.090 real seconds in the shell tool. It ran
the same sixteen finite schedule inputs against actual candidate method AST,
then eight direct event/timeout checks. It produced no modeled deadline miss;
matching expired owners were killed at .15, .25 or .30 virtual seconds. All
other extracted method AST hashes matched the first baseline. These virtual
times are not native durations.

The direct checks covered SPAWNED, OWNED, COORDINATOR and ORPHAN_KILLED with
original timeout 10 and .025. SPAWNED used .1 and .025 respectively. Other kinds
used the original object and value. All preserved subclass transaction hooks,
path/token/clock/boot fields, shared model state, one transaction and one append;
the original timeout never changed. The sixteen schedule cases also preserved
UNKNOWN after modeled lost replies, closed gates after failure, nonce uniqueness,
no same-INSERT retry, and blocking replacement while cleanup was unconfirmed.

Both invocations were first executions, with no failed-sample skip or rerun.
The old streams and old driver remain byte-for-byte intact. Each artifact
directory contains exact stdout, empty stderr, exit 0 and hashes. The candidate
driver pins exact runtime, original driver and first baseline stdout hashes
before extracting methods; it does not execute the old baseline.

## Exact hashes

- Base runtime SHA256:
  `46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`.
- Candidate runtime SHA256:
  `f2093101f7b7cf5eaa5604639a3892bcb0fd37f7421e171e242f6157416019ca`.
- Old driver SHA256:
  `58134735a8a25d84fbb566316ff4b163fa3e9f4013d56c4d1d55738a8d3df3b3`.
- Candidate driver SHA256:
  `7ece20b94e28b42fb14156913dd65630ef2fe85747d7b68f30ec0e7098929570`.
- First base stdout SHA256:
  `12ff60d87c5503ab947f243a3e3d021b2ecb742610119c4b69b0dd1de20641da`.
- First candidate stdout SHA256:
  `d92b0d185b8d9ca9834df89abf9c866131e36e904c65c2fb40789f1340560e36`.

## Remaining native evidence boundary

The fake registry transaction advances virtual time by its timeout, including
when its fake exception carries LOCKED or PROTOCOL. This is an explicit
conditional model assumption. Those native codes, internal WAL protocol
retry/backoff, disk I/O, process startup and OS scheduling do not have a hard
.1-second bound from `busy_timeout`. Cleanup joins and real child exit are also
modeled rather than measured. Arbitrary shard counts are not bounded by the
two-shard exploration.

PR 35 remains its original L1525 FAIL. Its pre-cleanup diagnostic shows the
monitor at SPAWNED registry connection setup and the original publisher waiting
for EX, but lacks enough local identity, phase-duration and syscall-result
evidence to prove that this conditional defect was its actual cause. Earlier
L1456 capture/undo failures remain a separate failure location.

Future native validation would still need the original exact bound PID/birth,
pidfd, inode-specific retained SH and zero-DML writer evidence, original
five-second lease/capture/recovery bounds, actual post-expiry kill/exit, a real
higher-generation owner and READY identity, original publication EX entry, exact
market receipts/digest and financial reconciliation. Monitor phase events would
need shard/PID and monotonic entry/return times plus native error classification
to separate registry stalls, unknown lease reads, kill outcome and observation
delay. No native execution, physical kernel stress, original-case rerun, push,
merge or production action is authorized by this report.
