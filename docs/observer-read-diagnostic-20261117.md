# Read-only observer diagnosis, 2026-11-17

This is diagnostic evidence, not eligibility evidence. It cannot change the
existing six-hour run's permanent live-coverage `NO_GO`, prove a financial
failure, or qualify production, capacity, stability or recovery.

## Scope and isolation

The implementation is an independent worktree derived from frozen observer
`ce3045f66456c1592858d0297f90a9552c7500dd`. The existing observer, producer
`763202df9cb3ce089721e5281371aff3eab58089`, original job, timeline and control
files remain unchanged by this diagnostic. There are no services, restarts,
signals to existing processes, writer constructors or repair operations.

`tools/diagnose_observer_read.py` defaults to newly created private synthetic
fixtures. It runs one child in `bwrap --ro-bind / / --dev /dev` with exactly
one new external output directory bound writable. The child verifies the
read-only mount before accessing a fixture, job or source. Its wall alarm is
8 seconds and the launcher timeout is 9.5 seconds. The output directory must
be new; existing observer output cannot be reused.

Live mode calls the original `Observer.sample()` once, without publishing its
result. A context wrapper calls the original `readonly(..., cold=False)` and
records safe metadata. It rejects any attempt to select the cold/immutable
path. The original sample may create a baseline only in the new private
diagnostic output. Its financial payload is discarded.

Saved observations contain database roles, logical phase, safe
module/function/line locations, error type, message digest, SQLite native
code/name, timing and WAL/SHM existence. Auxiliary-file inspection uses `stat`
only. No error messages, SQL text, keys, nonce, command IDs or absolute paths
are saved. The code never raw-opens an existing SQLite inode, copies a live
database, changes a journal mode on a live file, or creates/deletes its
sidecars. The sole direct `mode=ro` read outside the original helper targets
the newly created disposable cold-WAL fixture, inside the read-only mount.

## Original read path

The original helper checks the main file with metadata operations, waits up to
5 seconds for both WAL and SHM, opens normal SQLite `mode=ro`, enables
`query_only`, installs the read authorizer and starts a read transaction.
SQLite owns and closes the descriptor. A sidecar precheck does not make the
following SQLite open/read atomic with another process's sidecar lifecycle.

`Observer.sample()` reads checkpoint, router and financial shard, then brackets
the financial result with another checkpoint. A quiescent candidate requires
another financial read and checkpoint. The financial golden comparison is
not used on an inflight result. A failure before the stable bracket remains
unknown, with the existing coverage budget applied by the original observer.

## Captured results

The private synthetic experiment completed in **5.069 seconds**:

| Case | Sidecars before/after | Original/helper result |
| --- | --- | --- |
| Owned writer remains open in WAL mode | both present/both present | original read completed |
| Closed WAL fixture | both absent/both absent | original helper waited 5 seconds, then `ValueError`; no SQLite native code |
| Same closed fixture, ordinary SQLite `mode=ro` in kernel read-only namespace | both absent/both absent | `OperationalError`, native `14 / SQLITE_CANTOPEN` |

The ordinary cold-fixture error digest is
`fb017b1ae9cf0bb2aa77d824874a11be175f3816d6eb117d8de707c0a66014f1`, matching
the previously reported generic error digest. This demonstrates a compatible
failure mechanism. A digest of a generic SQLite message cannot identify the
unique cause of any earlier uninstrumented unknown sample.

The first requested live entry used a run root containing the nested `job/`
directory. It ended before opening a database because the top-level progress
file was absent. Its private redacted metadata is preserved separately;
it is not a database observation or a successful original sample.

After the integration owner confirmed the nested job path, the **one actual
live database sample** completed in **2.037 seconds**, on original driver
`122907 / birth 4679495`. It called the original sample in the original order:

| Read | Sidecars before | Sidecars after | Read duration | Outcome |
| --- | --- | --- | --- | --- |
| Checkpoint, first bracket | both absent | both present | 1.413 seconds | completed |
| Router | both present | both present | 0.00052 seconds | completed |
| Financial shard | both present | both present | 0.182 seconds | completed |
| Checkpoint, second bracket | both absent | both present | 0.343 seconds | completed |

The returned logical point was `inflight_or_unknown`; it did not enter the
stable-boundary golden branch. No exception occurred in this live sample, so
there is **no measured native live error code or proven live error cause**.
The metadata shows that sidecar availability changed between reads, while
the read-only namespace prevented this diagnostic from creating them. It does
not identify the process responsible for those changes. There was no further
live sample, polling loop or replay of a failed observation.

The two original observer modules were byte-identical to the frozen active
observer. Their SHA-256 values, the diagnostic implementation/test hashes,
runtime versions, redacted raw results and **38 passing tests** are retained
under `evidence/20261117-observer-read-diagnostic/`. Initial metadata failure,
synthetic fixture evidence and actual live evidence are separate artifacts.
`executed-diagnostic.py` preserves the exact script used for these samples.
The delivered script subsequently adds a sanitized outer entry-error envelope
and rejects regular standard descriptors before any mutation or output. These
two changes have direct tests; there was no additional live database read.

## Reproduction

Use a fresh private external output. The default starts no producer:

```sh
python -B tools/diagnose_observer_read.py --output "$NEW_PRIVATE_OUTPUT"
```

The explicitly scheduled one-shot live diagnostic requires all original
identity arguments and the actual job directory, not the run root:

```sh
python -B tools/diagnose_observer_read.py --mode live \
  --output "$NEW_PRIVATE_OUTPUT" --job "$EXISTING_JOB" \
  --source "$FROZEN_SOURCE" --frozen-commit "$PRODUCER_SHA" \
  --driver-pid "$ORIGINAL_PID" --driver-birth "$ORIGINAL_BIRTH"
```

Neither command appends to the continuous observer's timeline or coverage.
There is no loop or retry. Launching it is not a way to repair historical gaps.

## Minimal change proposal for separate review

1. Add the same sanitized native error code/name and bounded source locations
   to a future observer error envelope, retaining fail-closed unknown handling.
   This is the smallest diagnostic change; it does not solve availability.
2. Since the live trace shows changing sidecar availability, investigate a
   producer-owned idle SQLite connection for each observed WAL database. A
   persistent connection would have to keep sidecars available without holding
   a read transaction or impeding checkpoints; measure WAL growth, shutdown,
   worker restart and writer fencing before adopting it. Do not add raw file
   descriptors or let the external observer create sidecars.
3. Alternatively design a producer-owned consistent snapshot export with an
   atomic published manifest and explicit checkpoint/financial watermarks.
   Build it using legitimate SQLite transactions/backup, with private staging
   and measured cost. Never copy arbitrary live files or mark a live database
   immutable. Cross-database logical consistency still requires a protocol.

No active runtime fix is implemented here. A reviewed fix requires a new
frozen source, full relevant tests and a new continuous observation run; the
existing `NO_GO` is permanent. Rollback of this diagnostic consists solely of
not invoking it and removing its separate output/worktree after evidence
retention. It has no deployment or data migration.
