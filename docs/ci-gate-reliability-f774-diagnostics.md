# Bounded test-side diagnostics for the PR52 readiness gates

CODE_ONLY / NOT_RUN. The read-only review16ac950c retains the original
f7747c10 evidence and unresolved causes. This separate change adds diagnostic
context to two existing tests. It does not supply a new result for either test.

## Startup timeline

The existing test's WriterFence.renew observer calls the original function
exactly once. Its return object is returned directly; an original exception
uses a bare raise after an error-type/code-only marker. A failed marker is
caught and sets collection_failed, so marker failure cannot replace the
original outcome. Existing phases, requested.set ordering,0.3s wait,0.08s
sleep,0.4s fixture lease and all assertions remain.

The timeline holds at most64 records. Each carries a fixed stage label and
a nonnegative signed-64-bit monotonic_ns value. Error kinds and codes use
finite literal choices; no exception string/repr, token, owner, nonce,
generation, shard identity, path or lease record is added. Overflow marks
truncated and stops recording. Events cover the existing renew request/
return/error and main enter/construct/writer/wait/sleep/finish paths.

Clock reads and append operations add observation overhead, including within
the existing held writer interval. The timestamps are test observations, not
the authoritative CLOCK_BOOTTIME lease clock, a SQL gate-acquisition witness
or physical commit attestation. The bounded shared list is diagnostic only;
it supplies no locking or ownership guarantee.

## Same-query readiness projection

The existing final diagnostics call is saved once. Its original ready field
still controls the same assertTrue. Only when that value is false does a
helper build the assertion message. The helper retains fixed top/control
booleans, finite reason codes and aggregate true/false/unknown counts for six
worker gates. It includes at most the fixture's two dictionary rows and marks
truncation. Unknown values are represented by null, unknown counts or other;
arbitrary text and all identities remain out. Projection failure produces a
fixed diagnostic_projection_failed message and does not alter the ready value.

The earlier partial-publication checks, original snapshot payload and
observed_at, activate/wait_ready, query count,1s diagnostic budget,2s quote age,
1s worker lease, flags and assertions are unchanged. There is no extra query,
SQL, renewal, refresh, retry, thread/process start or process inspection.

## Validation and rollback

Preparation checked physical/Git bytes for the source closure and a clean
patch, without importing, compiling or running target code or executing SQL.
A separate group must review this CODE before root chooses a new explicit CI
scope. Old f774 failures remain source-pinned, and a later result must be
reported under its actual source and instrumentation.

Only these two test files change. All UTA runtime files and CI configuration
retain their f774 bytes. Revert the diagnostic patch to restore the prior
test messages; preserve first failure evidence. Root cause, runtime recovery,
capacity, production and real-funds acceptance remain open.
