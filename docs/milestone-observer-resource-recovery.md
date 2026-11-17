# Observer and resource recovery candidate

This candidate combines the reviewed durable batching and NORMAL cache foundation
with its independent observer and long-run supervisor. It is a synthetic-data,
single-node engineering release candidate. Production, real-funds, HA and 10,000/s
acceptance remain blocked.

## Changes and compatibility

- Resource accounting uses one no-follow metadata read per discovered path.
  Only named ephemeral SQLite auxiliaries and atomic publication temporaries may
  disappear; missing required databases and permission or I/O failures still fail.
- The producer retains three idle, query-only WAL connections across worker and
  parent restarts. They hold no read transaction. The original main-file device
  and inode metadata must match before any connection is retained.
- The observer, its read diagnostics, coverage policy and owned supervisor are
  delivered with independent tests. This changes neither the financial ledger
  format nor the public admission policy. New managed borrowing remains disabled.
- The unused private WebSocket codec has no listener or financial consumer.
  Native credit V2 and the experimental performance variant runner are outside
  this candidate.

## Historical failure and acceptance

The original `763202d` six-hour attempt stopped at 2026-11-17 10:35:43 UTC
after 2072.722098933 active seconds and 513 of 5400 rounds. Its resource scan
reported a missing shard WAL. It remains NO_GO and must never be resumed or
relabeled as a six-hour pass. The stopped-copy component diagnostic establishes
only the narrower checks recorded in its original report.

`a35fd56` passed three local 1243-test suites but failed two of eight remote
jobs. The original two FAILs and one ERROR remain archived. The reviewed fixture
repairs are included here; historical failures are not rewritten.

This candidate requires a new clean immutable SHA, three complete local runtime
suites, all eight push/PR CI jobs, exact wheel/sdist verification, fresh installed
functional checks and archive omission controls. After those gates, run a new
60-second real TLS/matching/settlement/restart smoke. A separate, preregistered
six-hour attempt may then start with original clocks and complete coverage gates.
Neither a short smoke nor a partial diagnostic substitutes for the long run.

## Deployment and rollback

1. Keep the old source and all original job directories immutable. Build and
   install only from the selected candidate SHA into a fresh environment.
2. Use fresh private synthetic job, authentication, TLS and observer directories;
   run the documented qualification and managed-observer commands. Keep default
   batching/cache settings unless a separately registered experiment selects them.
3. Record process births, source and artifact hashes, original deadlines and
   prerequisite evidence before starting. Preserve raw logs and all unknowns.
4. On failure, stop only the newly owned process group using its bound identity,
   retain in-flight durable state and query original command IDs before retrying.
   Do not copy a live database or delete WAL files to recover.
5. Roll back by discarding the failed synthetic deployment and starting a fresh
   environment from the previously qualified artifact. Do not run an older
   writer against a capability-marked database or transplant old job state.

Detailed contracts: [managed observer](managed-observer.md),
[commands](managed-observer-commands.md),
[idle-reader review](managed-read-holders-independent-review.md), and
[original stopped diagnostic](../evidence/diagnostics/managed-763202d-stopped-component-01/README.md).

Independent code/component reviews are included. Full-candidate acceptance and
the new long run are pending; no financial-rule or live-launch sign-off is implied.

## First combined candidate: retained NO_GO

The first combined immutable source `bb34b5f` completed all three local suites:
Python3.12 and Python3.13 passed 1411 tests each; Python3.10 retained one ERROR.
Remote push 44082854090 and PR 44082861767 completed six successful jobs and
two Python3.10 jobs with the same ERROR. The test referenced a SQLite module
constant absent from Python3.10; the diagnostic runtime already handled missing
native exception metadata. Original reports and failed ZIPs are retained.

The new test-only compatibility repair checks actual native exception fields
when available and null when absent, without relying on module constants.
It adds real exception and module-proxy call-through controls. Independent
short tests passed nine cases on each of three runtimes; integration independently
passed the same nine on Python3.10. Diagnostic and financial runtime bytes are
unchanged. The repaired source still needs new complete QA/CI/package gates.

The bb34 package independently passed its limited exact-artifact scope (2536
tracked files, 52 runtime files and eight actual omission controls). This package
result neither cancels bb34's QA failures nor qualifies the next source commit.
