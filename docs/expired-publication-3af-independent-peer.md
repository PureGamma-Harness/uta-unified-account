# Independent static peer: expired-publication fixture

Reviewed immutable proposal749e37ac90933b5d0037ca16e559972e224ca9b8 and
its writer-availability addition3af589415ccfdb65ed84a952184a77030319a3df
in a separate review tree. **No additional static blocker was found for the
integration owner's single bounded candidate component run**, under the exact
result conditions below. This is not native PASS, full qualification or
production approval. The reviewer ran no SQL, service or actual fault case.

## Identity, capture and cleanup

The fixture selects its own unreaped shard0 child under the router mutex and
opens its pidfd. The helper checks PID/start ticks/boot/UID before and after
reading that selected PID's fdinfo. Device/inode and the exact router-lock
path bind the descriptor to the original private file. The required kernel
record is full-file FLOCK/ADVISORY/READ for that selected PID, not inference
from another owner's EX contention. The other shard is not paused.

The selected pidfd receives SIGSTOP; the same process must actually be T and
retain the bound kernel READ. An actual nonblocking EX attempt must still be
blocked. A lost capture or busy SQLite writer can resume only that bound,
living, still-active original owner within the existing five-second/eight-
observation setup bounds. Fatal/unknown probe errors do not qualify another
capture. The .1-second unexpired control requires no original pidfd exit,
the same active generation and the retained READ, so it cannot pass by
prematurely killing an unexpired owner.

Signals target pidfds. The final fallback kill is restricted to the original
bound child and is explicitly marked, while normal own-process cleanup stays
with the existing router. A failure before publication either resumes the
same still-active original owner or leaves the failed case to its own router
cleanup; it never adopts or signals a foreign PID. A cleanup exception or
watchdog must stay failed/UNKNOWN, not be reclassified as native success.
The recorder's outer new process-group/subreaper boundary covers only its own
experiment; this does not prove behavior under watcher death or kernel I/O
that cannot be interrupted.

## Writer-probe closure

The749 proposal could stop SH while the child also held a SQLite financial
writer. In3af, `mode=rw` requires an existing database, timeout0 avoids waiting,
and only BEGIN IMMEDIATE/ROLLBACK are executed. No owner token/UDF is installed
and no DML is issued. Success requires a real transaction followed by rollback,
no active transaction and unchanged total_changes. Native integer base-code5
BUSY (including extended BUSY), or exact built-in Python3.10 OperationalError
with no native code and only `database is locked`, classifies a failed capture.
LOCKED, I/O, schema, permission and other errors propagate. The probe closes
before the original business enqueue. Zero DML is not a claim of zero SQLite
filesystem/locking activity, and this reviewer did not execute the probe.

## Recovery clocks and actual receipts

The five-second lease is the real configured production default from first
acquisition for this case only; acquisition-event expiry-minus-observation
must equal5,000,000,000ns. Other cases retain their prior one-second lease.
The paused token is not renewed or edited. Publication begins after a genuine
remaining-time observation<=.25s, still active; its own entry rechecks that
same owner and generation. Snapshot version2 retains its original bytes and
digest throughout. There is one original API publication call, timeout5.

Three independent milestones remain within publication-start+5 seconds:
old bound pidfd exit, a persistent new active generation, and the original
publisher thread's genuine first EX acquisition. The call-through wrapper
only records acquisition after the original lock actually succeeds. The
initial gate, receipts and final gate retain their original API phase limits.

**The15-second deadline also waits for completion on the success path.** It
is a publication-thread lifecycle bound, not only a cleanup delay and not a
five-second end-to-end publication guarantee. A result must not be labeled
“publication completed within5s” unless its actual completion timestamp also
proves that separate claim. This distinction is essential when describing
recovery SLOs or comparing the original historical failure.

Both original per-shard publication CIDs must have exact persistent SUCCEEDED
receipts and original local payloads, with no replacement order/publication
ID. Original ledger events/postings/balances, principal/interest liabilities,
fills, positions, matches, schema and configured cache values must stay
unchanged. Orders and ORDER_ACCEPTED events are each at most one and the
order identity must match the original account and command. The original
business command's initial PENDING ACK is not proof of later admission or
settlement; this fixture does not claim that completion measure.

## Result envelope and pure controls

The trace launcher returns the worker's exit code as-is. Exit0 alone is
insufficient because logger failures and forced residual-child cleanup are
separate fields. Before accepting the actual run, independently require:

- case passed, original assertions intact and logger_failures empty;
- no watchdog, no forced cleanup and every owned child's pidfd exited;
- all three five-second milestones and exact receipt/financial assertions;
- preserved failed/UNKNOWN output and actual source identity.

The original historical assertion is matched by its explicit text instead of
calling every earlier setup failure a reproduction. The original13:02 held-
False result therefore remains NO_REPRODUCTION of the later done.wait5 fault.

Thirteen original reviewer vectors exercised the exact helper AST with
synthetic process identity and temporary fdinfo text. They cover full-file
READ, tabs, foreign PID, WRITE/POSIX/blocked records, partial ranges, wrong
inode/device, malformed inode and changed birth at the final identity check.
All passed in0.0044s on CPU3. Path mapping touched only temporary files; it
queried no actual /proc process or SQLite authority and proves no native lock
holder. The helper is the system under test; expected outcomes are literal
reviewer values rather than a copied production oracle.

Every runtime/packaging path matches the original d421 source; existing class
methods differ only in the requested fault case and its case-specific setUp
lease selection. The recorder and two pure test helpers are test/evidence
scope. No frozen author source or original case was modified by this review.

Evidence and the reproducible pure control are under
`evidence/reviews/expired-publication-3af-peer/`. Rollback of this review is
docs/evidence-only. Any candidate test-code rollback must retain original
results and must not modify authorities, leases, CIDs or financial balances.
A successful single native component still requires a new immutable source,
full local QA, remote CI and fresh package gates before broader acceptance.
