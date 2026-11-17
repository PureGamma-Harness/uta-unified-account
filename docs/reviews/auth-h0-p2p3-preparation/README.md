# Independent P2/P3 preparation — no dynamic result

This commit adds only independent test code and review documents after
`76a435c28836dadf86e9967088d81600cc79671c`. Both new probes remain **NOT_RUN**.
The preparation check parses files as Python 3.10 AST and enumerates small
independent policy models. It does not import these harnesses or product code,
open an AuthDB, execute SQL, create a profile/key, or run a probe. Those static
models are not independent dynamic acceptance of the implementation.

`static-first.json` preserves the first pure check before adding CPU4 affinity
to the short starter; `static-final.json` binds the committed code. Both are
preparation-only, and neither starts a test or creates financial authority.

The future source is exactly `912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a`;
all 64 materialized `uta/` files must equal runtime
`5750e12d60dbf7f8414b4e837e076a60c93a23bc`. The QA checkout may have its
Git-public historical `evidence/` directory sparse. Each future admission verifies
only that exact Git HEAD, a clean status, and all 64 runtime blobs; it does not
describe the current QA checkout as fully materialized. No old private DB or
request is used. Frozen909 and every first RED/UNKNOWN/P1/full3 record stay intact.

## P2: fixed default total-handle characterization

The fixed target is **262 actual signed requests**: 224 original admissions,
32 authorized read queries, five expected refusals, and one later new admission.
It uses default constructor arguments, one issuing thread, a fresh AuthDB,
independent literal canonical-array/HMAC construction, real constructors/grants,
and retained opaque observations. Every successful inspection checks all three
authorization flags are literally false.

The seven required steps are: retain224 ordinary observations; refuse the225th
ordinary request without another acceptance; deny a valid-MAC ungranted query;
retain32 current-read queries at total256 preserving the immutable original;
refuse query33; refuse a new ordinary request at total255 and total224; and admit
one new ordinary request only after total223. AuthDB acceptance rows are224 at
the full-boundary stage and225 after the final distinct CID. Four handle-capacity
refusals and one permission refusal must each consume one fresh nonce with one
expected audit outcome and no new acceptance. The successful32 queries do not
change the first acceptance. All retained observations are released by their
own issuing thread at the end, also on an incomplete prefix.

The reserved32 is conditional on an available intake token and reachable AuthDB.
`_reserve` compares total retained slots, with ordinary threshold224 and query
threshold256. It does not maintain independent class counters. Fully exhausted
global intake can return typed503 `credit_auth_intake_capacity`; unavailable
storage can also prevent a query. Neither constitutes a previously promised
unconditional query availability guarantee. This test does not exhaust intake,
claim DoS resistance, or change runtime/financial policy to create such a promise.

The first32 ordinary admissions are part of the fixed224 target, never discarded
warmup. Their elapsed time and conservative projection are written once. The
projection includes quadratic growth of scanned history and the final8 marginal
costs; it is a budget guard, not a measured final duration or throughput. If the
projection exceeds25s, or the work deadline is reached, the probe stops
**NOT_COMPLETED**, retains the actual prefix, releases its own handles, and leaves
uncompleted steps unaccepted. It never shrinks the target, retries to green, or
turns a prefix into a default224+32 pass. Planning data budget is32MiB above the
existing shared free-space floor17,448,304,640B. Actual use/duration are unmeasured.

## P3: after-COMMIT-return response loss

Only one newly owned worker is created. The parent first creates a fresh AuthDB,
real profile and grants, with zero acceptances. The worker uses a fresh public
issuer and independent literal-MAC signer, sends only safe bounded READY identity
metadata, and waits for exactly `GO\n`. The parent binds the actual Popen PID,
birth, boot, UID and pidfd before GO. No key, nonce, signature, headers, receipt,
or DB is written to a public file or stdout.

The worker performs one real public `capture`. After that call returns normally
and the returned opaque observation is inspected, it writes/fsyncs an exclusive
private marker, fsyncs that marker's directory, then calls `os._exit(73)` before
an application response. The marker records observation of a COMMIT-return path;
its clock is **not a measured physical COMMIT epoch**. The parent must actually
wait/reap exit73 and correlate the marker with the one persistent acceptance.
A newly constructed issuer then performs a current `credit.read` lookup and a
new-nonce same-CID retry. Both must be query-only with the identical first payload,
one total first acceptance, three actual consumed request nonces, one FIRST_ACCEPTED
and two QUERY_ORIGINAL audits, and every authorization flag false.

Readiness is bounded3s; completion after GO is bounded5s. The worker has an
independent10s self-alarm and exits on EOF/non-GO input without starting capture.
Only a pidfd with matching newly owned process identity can receive TERM, then
KILL after a bounded1s wait, then another1s wait/reap. There is no PID-number,
process-group or unrelated-job fallback. Every forced cleanup stays **UNKNOWN**
even if later queries could resolve a row. An unbound/missing identity is UNKNOWN,
not permission to search or signal other processes. Partial READY bytes are kept
privately even on failure; raw is called final only if its owner was reaped.

This covers an application process losing its reply after AuthDB COMMIT returned.
It does not inject mid-COMMIT failure, storage loss, power loss, a financial source
command, actual loan, public HTTP timeout, or HA/RPO behavior.

## Detached execution and cleanup budget — future commands only

Root must separately authorize each exact bundle and one fresh outer directory.
No command below has been executed for P2/P3. The launcher `start` exclusively
creates a0700 directory and returns the actual supervisor identity promptly.
Long-lived supervisor streams use exclusive private files and stdin DEVNULL,
with `start_new_session=True`; they do not depend on an exec-server session.
The supervisor sets CPU4 and binds its direct subject with pidfd. Watchdog27.5s
reserves2.5s within the hard30s budget for bounded cleanup, raw fsync/hash and
result fsync. Completion is accepted only with actual child wait/reap, correct
probe steps, unchanged source/bundle, and measured time<=30s. Later completion
record serialization is explicitly outside that recorded clock, not invented.

On watchdog, the P3 supervisor may signal only the worker recorded by its direct
subject, with exact subject-parent/worker PID+birth+boot+UID and a still-matching
direct-child relation before pidfd binding. The supervisor is not that worker's
parent and does not claim to reap it. It then kills/reaps only its own bound
subject. Missing binding, failed reap, forced cleanup, supervisor disappearance,
or absent completion retains UNKNOWN/incomplete evidence. The worker's self-alarm
and stdin EOF are additional bounds, not a fabricated proof of cleanup. No old
PID, source tree, original AuthDB, or unrelated job is modified. A supervisor may
itself become a reparented zombie; the short starter makes no supervisor-reap claim.

Planned P2 command, CPU4 subject with hard30s including supervised cleanup:

```sh
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -I -B \
  /workspace/uta-auth-h0-p2p3-preparation/docs/reviews/auth-h0-p2p3-preparation/detached_supervisor.py start \
  --kind P2 --source /workspace/uta-auth-h0-qa-912f2a4 \
  --bundle-root /workspace/uta-auth-h0-p2p3-preparation \
  --outer /workspace/uta-auth-h0-independent-private/default-handles-912-first-actual
```

Planned P3 command, separately authorized after review, planning private budget16MiB:

```sh
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python -I -B \
  /workspace/uta-auth-h0-p2p3-preparation/docs/reviews/auth-h0-p2p3-preparation/detached_supervisor.py start \
  --kind P3 --source /workspace/uta-auth-h0-qa-912f2a4 \
  --bundle-root /workspace/uta-auth-h0-p2p3-preparation \
  --outer /workspace/uta-auth-h0-independent-private/process-replyloss-912-first-actual
```

After any disconnect, query the original outer's status/recorded identity first;
never resubmit either `start`. Exclusive creation deliberately prevents rerun in
the same directory. Failed runs/UNKNOWN remain original artifacts. Future public
evidence must use an explicit safe field allowlist; exact requests/profiles,
actual keys/nonces/signatures, private stdout/stderr, markers and DBs remain private.

## Suitable public Draft scope, after root publication checks

Suggested wording: “Experimental H0 authentication-only ingress, default off.
Disabled construction returns501. A fresh authentication-format2 store records
MAC/nonce/grant observations and immutable first-CID identity; all observations
retain financial/source-delivery/execution authorization=false. This does not
enable an HTTP route or financial command source. Independent data-integrity fixes
and four observed AuthDB ordering schedules have scoped evidence. Three exact-source
inner unit-test summaries each report1823 passes across Python3.12/3.10/3.13; the
original outer controller lost its third outcome and matrix summary, so outer
orchestration remains recording-incomplete. New default-capacity and process
reply-loss cases are prepared but NOT_RUN. This Draft is not full H0, H1+, product,
release, throughput, HA or production acceptance.”

Remaining real gates include both directions/more schedules of profile/grant/revoke
and current-read races, executed P2/P3 (including Python3.10 execution rather than
AST alone), unknown/mid-COMMIT and storage failure semantics, operational rollout
and compatibility review, clean public history/artifact inspection, and explicit
later-stage approval for any financial source or public endpoint. Existing full3
inner results do not replace those gates. This commit does not push or open a PR.

## R3 preparation revision after cc74 — still NOT_RUN

The initial cc74 commit and every original static result remain in history.
`r3-supervisor-revision.json` supersedes only its supervisor SHA; all three shared
support/P2/P3 harness hashes, the262-request target and the commands/budgets above
are unchanged. No P1/full3 rerun or AuthDB execution accompanies this revision.

After direct subject Popen returns, the supervisor now immediately enters its
try block with owned metadata initializedNone. It first opens pidfd while this
sole parent's new direct child is still unreaped, before any fallible `/proc`
identity read or save. That descriptor stays in local binding state if a later
metadata/record step raises. The primary error and bounded cleanup are recorded
separately as UNKNOWN, with an early exclusive unknown record attempted before
later result inspection. A bound direct-child descriptor may be killed/reaped
even when optional metadata failed; an unavailable descriptor permits no PID or
group fallback. Raw hashes remain final only after actual wait/reap.

The starter now fsyncs an exclusive `launch-intent.json` before Popen. This intent
alone is not proof that Popen succeeded. After Popen returns, identity/save errors
produce START_OCCURRED_RECORD_UNKNOWN rather than “not started”. A separate
exclusive unknown-record write is attempted, and the first error survives any
secondary write failure. The existing outer directory, intent, private streams
and independently written supervisor-owner remain possible recovery inputs;
their absence/presence is inspected rather than inferred. In particular a failed
post-start record is never authorization to repeat `start`.

`check_r3_fake_owned.py` extracts only four supervisor helper declarations into a
namespace of pure fakes, without importing the supervisor or starting processes.
Eight cases cover fd-before-identity, failed identity, failed fd binding, failed
signal/wait cleanup, and starter identity/one-write/two-write failures. These are
control-flow simulations, not injected real process failures or dynamic AuthDB
results. `r3-fake-owned-first.json` preserves the first pure run; the final pure
run additionally pins the exact supervisor SHA. Both P2/P3 stay NOT_RUN until root
authorizes their exact revised bundle one batch at a time.
