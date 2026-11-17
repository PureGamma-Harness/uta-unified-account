# Fixed ABBA16 actual diagnostic result

The separately authorized experiment ran once at exact observation source
80fae18c7afafdbb0145e5e8b44741323994b74f on 2026-11-17, finishing at
15:33:08.844121 UTC after 125.852420290 seconds. All sixteen preregistered samples
ran in ABBA order repeated four times. A and B each had eight original testcase
PASS results and complete technical gates. There was no warmup, repeat, discarded
sample, unexecuted slot, extra SQL, source/runtime change or production fix.
Classification is **diagnostic NO_REPRO**, not source91 qualification or resolution
of its original CI five-second failure. The historical root cause remains UNPROVEN.

Exact execution targets were final controller SHA-256
5ce9884cfd39238482c0282cf357aab52497b7fbacb395505eecb97f67eec15e and final
registration SHA-256
e5b67407cc1ddec6e2b85bd96037649f8803d0e714b99ff15a95f867e717b13e.
The immutable source/runtime bindings, ordinary FAIL continue and technical-stop
rules, policy amendment and original five-second/fifteen-second limits remained
as approved. Original proposals, independent red vectors, b570's first incomplete
observation and the failed CI raw were not overwritten or relabeled.

A actually ran system Python3.13.5 with its Python core embedded in the pinned
executable and no mapped libpython. B actually ran prepared official Python3.13.18
with the pinned prefix libpython and process-local LD_LIBRARY_PATH. Both reported
SQLite3.46.1. Every actual worker's start and result matched its registered version,
executable, flags, environment, CPU2 and mapped-library hashes; provider archive,
executable and library posthashes remained bound. B's GCC13.3.0 build/host differs
from the failing CI's GCC15.2.0 build, kernel/image/libc. These observations do not
isolate Python version as a unique cause.

All sixteen whole sample durations, including the outer check covering END I/O,
were between 7.234105354 and 8.580588520 seconds. Every original testcase retained
its original lease5, capture5, recovery5, API-phase5 and full publication lifecycle15
budgets. Native SH capture to old bound PID exit ranged from 4.207443064 to
4.815680910 seconds; capture to publication completion ranged from 4.961727442 to
5.654073031 seconds. The later publication-start clocks are retained per sample;
they must not replace the stopped-owner wait when discussing recovery behavior.
These are individual synthetic fault diagnostics, not capacity or latency-SLO
acceptance results.

There were 5,190 observed original native status calls and zero native status
exceptions in this batch. All 32 observer post-join records were explicitly
nonalive, with original start/end/no-error lifecycle evidence. All 48 worker
spawns were accounted for and had real final pidfd exits. Sixteen original
supervisor expiry kills had their actual expired native lease witnesses; no
MainThread fallback, fixture forced cleanup, external forced signal, watchdog,
logger/sampler unknown or technical stop occurred.

All 32 target publication CIDs had real SUCCEEDED receipts. Every original
case reached its financial assertions: zero orders and zero accepted events,
unchanged ledger/debt/fills/positions/matches, and unchanged original schema/cache
versions. A held PENDING command is not reported as financially accepted or
settled. No independent database reopening or extra financial SQL audit was
performed by this diagnostic collector; the original test's assertions and
actual event records are the stated evidence boundary.

Each sample's actual child preflight and source-before/after matched all 266
original source members. The final read-only audit also compared all 52 tracked
uta runtime files byte-for-byte against Git source91, including files outside
the 266-member map. Source remained clean at exact80fa during execution. A final
read-only /proc scan found no members of any of the 32 fresh launcher/worker
PGIDs or SIDs. Other jobs, frozen sources, nonces and process affinity were not
modified. CPU2 was released when the batch ended.

The public-safe archive is
`evidence/runs/recovery-horizon91/ab16-80fa-actual/`: 327 original files totaling
9,221,279 bytes, copied byte-for-byte from the new batch and outer output roots.
`ab16-80fa-sha256.json` pins every raw member. The original root paths were
`/workspace/uta-recovery-horizon91-ab16-final-20261117-01` and its `-outer` sibling.
The original registration, full raw sample results, both whole clocks, native
exceptions/receipts, source maps, runtime/provider identities and all event
records are retained. `verify_ab16_archive.py` performs archived-file checks only,
without SQL, process actions or a testcase; its saved result has nine global and
160 per-sample checks true. Independent peer review is separate evidence.

To reproduce, restore exact approved sources, prepare the pinned B archive using
the provenance98e procedure, then request a new bounded experiment against a
fresh private output path. Never reuse these output roots or count this batch
as a qualification rerun. This evidence-only delivery has no production schema
or deployment migration; rollback is to stop using the optional diagnostic
helpers while retaining all original raw evidence. Source91's historical CI
NO_GO and production approval status remain unchanged.
