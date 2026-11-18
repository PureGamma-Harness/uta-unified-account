# Independent CI gate diagnostic CODE review

**NOT_CLOSED_STRICT_TIMELINE_CAP** for immutable source
aeb5f23934fba8efc1ffd7b27c702a1b596bd228. No target was imported, compiled,
tested or run. No execution GO is granted.

The ten canonical regular physical/Git input pins total323,524 bytes and match
the frozen0ac93bfd plan. They are five inspected UTA modules, four tests and
one document; this does not claim61 physical runtime inputs. All61 UTA Python
Git blobs and CI configuration retain their f7747c10 values.

## CI-DIAG-AEB-001: shared timeline can exceed its exact limit

The main and keeper threads both call mark. The source separately checks
len(timeline)<64 and later appends. Its existing financial write gate does
not enclose both complete marker operations: renew_request is observed
before the original renewal attempts that gate.

A source-level permitted interleaving is:

1. There are63 records and truncated is false.
2. Main passes the length check and is suspended before append.
3. Keeper also passes63<64, then appends the64th record.
4. Main appends the65th record.
5. If those are the final two markers, neither sets truncated.

This is static interleaving reasoning, not an executed counterexample or a
claim that it caused either historical CI failure. With only the two declared
non-reentrant producers it shows an off-by-one cap, not unlimited growth or
financial corruption. Nevertheless, the declared maximum64/accurate-overflow
contract is not enforced by this source.

Resolution needs an auditable bounded recording mechanism for every permitted
interleaving, with accurate overflow and no new financial locks, queries,
refreshes or retries. Preserve the original renewable call/return/exception,
timing thresholds and account assertions, then freeze a new source and plan.

## Preserved behavior and finite readiness projection

The renewal observer calls the captured original exactly once, returns the
same result object and uses bare raise for its original exception. Marker
failures are caught and set collection_failed. The17 marker labels are
literal callsites, with validated signed64-bit nonnegative clock readings.

The original flags, requested-event ordering, wait0.3/sleep0.08/fixture lease0.4,
enter/construct/check/writer/finish flow and assertions remain. Marker work
adds real overhead, including inside the held financial writer interval.
Those observations are not authoritative lease time, SQL-gate acquisition
or physical-COMMIT evidence; append order is not a proven cross-thread time
order. Original describe_error behavior, including old message formatting,
is untouched. Finite/anonymous claims concern the new fields only.

The readiness test retains the same one final diagnostics query and asserts
its original native-bool ready result. Only false invokes the new projection.
Exact dict/list/tuple and bool/str checks yield finite top/control flags,
whitelisted reason counts and six gate counts from at most two dictionary
rows. Unknown values become null, unknown or other. No PID/nonce/generation/
shard/path/full report/market digest or arbitrary string/repr is copied.
Projection exceptions return fixed JSON; no new query, SQL, renewal, snapshot,
activation, refresh or retry is introduced. This conclusion relies on the
inspected provider's ordinary bool/dict contract, not arbitrary objects with
side-effecting truthiness.

The readiness sub-scope and original call/exception/threshold conservation
are limited CODE closures. They do not close the shared-buffer finding.

Historical f774 first failures and their unresolved causes stay intact.
This review supplies neither a reproduced failure nor a new runtime or
performance result. Root still needs revised CODE review, a separate exact
run/CI decision and independent original evidence review. Capacity,
production and real funds remain NO_GO.

Only administrative standard-library text/byte hashing and Git reads were
performed. The verified-new independent review worktree is the only index
initialized; source/primary worktree indexes and authority data were untouched.
