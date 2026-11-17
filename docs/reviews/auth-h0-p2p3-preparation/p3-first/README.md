# P3 first actual — application reply loss after AuthDB COMMIT return only

Decision: **ACCEPT_P3_AFTER_AUTHDB_COMMIT_RETURN_APPLICATION_REPLYLOSS_ONLY**.
One exact R3 supervisor670bd0a / P3 7fd73d8 / support5498be6 run completed3/3 steps
on source912/runtime5750, Python3.12.14 and SQLite3.53.1. The original P2/P1/full3
records and all prior RED/UNKNOWN were neither modified nor rerun.

The fresh fixture had zero initial acceptances. One actual new worker reached
bounded READY, with real Popen/PID/birth/boot/UID and pidfd binding before GO.
It invoked public capture with a real independent literal-MAC request. After the
call returned, the worker inspected the opaque observation, fsynced the exclusive
private return-observation marker and its directory, then self-exited73 before an
application receipt. The parent actually waited/reaped73, without a cleanup signal
or forced termination. Its fresh public issuer then queried with current credit.read
and retried the same CID using a fresh signed nonce. Both were query-only and
preserved the sole first-acceptance identity. All observed authorization flags
were literallyfalse; the final AuthDB has one first acceptance and three consumed
request nonces. This is an auth-only state observation, not a loan or source command.

The outer measured778,994,900ns after raw/result fsync and before later completion
record serialization; the inner probe recorded326,733,807ns before report write.
The actual subject437263/birth8630300 exited0 and was waited/reaped by supervisor
437182/birth8630281. The subject's actual worker identity is bound in safe JSON.
The supervisor reported no watchdog or primary control error, with runtime/harness
unchanged. Its short starter does not claim supervisor wait/reap. Later process
observations are separate from actual parent/child reaping records and never
reconstruct missing historical process metadata. Worker CPU4 affinity follows
from the exact parent affinity/inheritance path; it is not a departed `/proc` read.

An independent postcheck opened only this completed own DB via URI mode=ro,
query_only, and one consistent snapshot, with no product import/constructor or new
auth request. It independently reconstructed all three private canonical arrays
and HMACs, linked each to exactly one audit/nonce, checked first acceptance1/query2
with the original identity and correct current read grants, four grants, empty FK
check, and all retained acceptance flags false. It linked the private marker,
single READY stdout line, parent/worker identity and actual exit73/reap proof.
Every original private file hash stayed unchanged. Only explicit safe counts,
identities and artifact hashes are copied to this folder; actual requests, keys,
nonces, signatures, profile, receipts, DB and raw streams remain private.

The cleanup record's `identity_verified:false` describes the unentered forced
cleanup branch: normal exit73 was already reaped. It does not negate the separate
READY/Popen/pidfd/marker identity checks. GO has no separately persisted timestamp;
ordering evidence is the fixed source path plus actual READY, marker and exit73.
The marker clock observes a returned AuthDB call and is not a physical COMMIT epoch.

This does not test mid-COMMIT ambiguity, forced-cleanup recovery, power/storage
loss, financial settlement, HA/RPO, public HTTP delivery loss, Python3.10 runtime
execution of P3, or all concurrency orders. No disconnect was injected into the
detached controller. No new production, release or full H0 acceptance follows.
The original full3 missing outer outcome/matrix remains recording-incomplete.
