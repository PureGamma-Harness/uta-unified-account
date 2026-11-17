# P2 first actual — default retained handle thresholds only

Decision: **ACCEPT_P2_DEFAULT_RETAINED_HANDLE_THRESHOLDS_ONLY**. Exact approved
R3 supervisor670bd0a / P2f2ecd948 / support5498be6 ran once on source912/runtime5750,
Python3.12.14 and SQLite3.53.1, CPU4. This is not throughput, production or full H0
acceptance. Queries were tested with global intake and AuthDB available.

All seven fixed steps completed, with262 actual signed requests:224 first-stage
admissions,32 read queries, four handle-capacity refusals, one permission refusal,
then one distinct-CID admission after releasing below total224. The final AuthDB
has225 first acceptances. Normal admission remained refused at total255 and224;
32 query observations were retained with the224 original ordinary observations.
The implementation uses total slot count rather than independent class counters.
The first32 actual retained admissions took0.180794612s, projected13.1195950646s,
and remained part of the original224 target. Nothing was discarded or retried.

Supervisor interval:2026-11-17T20:56:00.176427Z to20:56:02.032976Z; recorded clock
after raw/result fsync:1,856,552,275ns. The inner probe recorded1,388,966,848ns before
report write. Completion-record serialization follows the recorded outer clock.
Actual subject431704/birth8608682 exited0 and was waited/reaped by supervisor431623/
birth8608660, with pidfd bound, no watchdog and no primary control error. A later
read found that exact subject absent and supervisor Z/PPID1/kernel encoded exit0;
the short starter does not claim it reaped the detached supervisor. This run did
not deliberately sever an exec-server connection.

An independent postcheck used one consistent URI mode=ro/query_only AuthDB snapshot,
no product import or constructor, and no additional auth request. It reconstructed
literal wire arrays/HMACs for all262 retained private exact requests and linked
each to exactly one persistent audit and consumed nonce. It checked225 first
payloads/audits,32 query-original identity links, five refusal outcomes, four grants,
empty foreign-key check and all acceptance authorization flags literallyfalse.
Every original private file hash remained unchanged by that check. The source's64
runtime files and exact harness hashes were rechecked. The postcheck is separate
verification work and does not alter the original execution timing.

`actual-safe.json` and `readonly-check-safe.json` are explicit aggregate/hash
allowlists. Actual keys, nonces, signatures, profiles, requests, opaque observations,
DBs and raw streams remain in the original0700 private directories. This evidence
does not prove intake-exhaustion query availability, cross-thread handles, all
concurrency orders, Python3.10 execution of P2, unknown/mid-COMMIT behavior or HA.
P3 is NOT_RUN as of this P2 sealing record and requires its own separately granted
execution. No P1/full3 rerun, financial source, endpoint or production approval.
