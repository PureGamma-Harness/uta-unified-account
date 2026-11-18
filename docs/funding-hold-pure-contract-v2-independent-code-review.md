# Independent CODE review: pure funding hold contract v2

Decision: PASS_STATIC_NO_BLOCKER for
ed81c424e3be7c004331bcd8340421d60063fcb6, exact parent
2bb8095faa76ca7d18f957590c7816ba44018554. The implementation matches the limited
pure D1 v2 contract at source level. All 29 tests, actual target behavior and
independent reference comparison remain NOT_RUN. This report grants no CI,
target execution, financial activation or production permission.

Rule approval is a separate artifact: 86b3c2ac0b41b526cf8ebba2b3babda0b4b97ad1
accepts 2bb8095f as ACCEPT_FOR_CODE_ONLY_LIMITED_PURE_D1_V2. It did not validate
ed81 or run target/reference code. This CODE review uses that stated contract;
it does not convert its limited rule approval into numerical or runtime evidence.
The original candidate, limited review 7519ace0 and wire895 remain historical.

## Immutable patch and source inventory

Five changed paths match author-worktree and Git bytes. Four declared content
pins match, and the companion JSON pins all five paths. Only advance_stage and
preview_wait change within the pure module; 32 other function/class definitions
and all imports retain identical ASTs. All original 66 runtime Git blobs equal
baseline C d1fd381bde923dc4010977058b76e34d6162e9a9. Source evidence here is Git
closure, not a full physical deployment preflight in the sparse author checkout.
Both wire895 files retain their exact Git bytes.

The test inventory explicitly adds V4=V3+funding_hold_pure.py. V2's 62-member
literal and V3's 65-member expression retain identical ASTs. V4 has exactly 66
Python names and equals the reviewed Git source set; the existing HTML asset
makes 67 current runtime members including the new pure module. Observed names
are still compared to the literal allowlist. The allowlist is not built from
the observed directory. Credit artifact format, live-code exclusions, service
dispatch, old-authority migration and financial defaults are unchanged.

## Complete stage CAS

The required keyword-only signature accepts expected_revision and
expected_active_stage, with no default or catch-all compatibility arguments.
The old single-ref keyword has no conversion path and is intentionally rejected
by the signature. Current state and proposed Stage are validated first; revision
must be a native integer. _link validates the exact expected Stage, its native
fields/references and duty/rule association before the CAS comparison.

Stage dataclass equality compares kind, amount, exposure_ref, cap_ref and
final_ref; each ContentRef also has validated native fields. Both complete Stage
and revision must match. A foreign expectation cannot hide behind a shared cap
digest. A well-formed different exposure, amount, cap or kind conflicts without
returning a replacement. Final-state immutability, proposed lineage/cap bounds
and frozen history construction remain unchanged. The caller's input objects
are not mutated. This is a check on supplied immutable data, not authenticated
cut content, authoritative history or a durable atomic CAS.

## Wait no-op and checked revision

Validation of native values, policy/revision CAS and nonregressing supplied time
precedes any return. The candidate computes high-watermark, attempts,
last-dispatch and sticky default before deciding whether the record changes.
Action, policy, start and deadline are held constant by construction, so equality
of those four proposed fields means all nonrevision record fields are unchanged.
Only then is the original record returned with the same revision and no counted
query, in both WAIT and DEFAULT_REVIEW.

For a changed record, revision+1 is checked before constructing the replacement;
there is no saturation. Same time alone is insufficient: newly recognizing
deadline/attempt exhaustion changes default, and must fail at maximum revision.
An already-default same-time projection remains unchanged even if dispatch was
requested, because no new query is eligible. A new high-watermark is a change.

Spacing equality remains eligible only before deadline and below the cap. At
deadline equality, no query is counted. The last permitted query is counted and
sets default; existing attempts are never refunded. Original start/deadline and
input records remain unchanged on rejection. No clock is read and no query is
actually sent by this pure function. D2 must persist counted attempts/outbox
before dispatch and preserve unknown outcomes.

## Test definitions and independent limits

The entire original test module retains identical AST after removing the seven
new definitions and ignoring only eight expected-stage keyword migrations across
the existing methods and two helpers. Its 22 original methods and assertion
values are preserved. Seven new definitions check specific stale/foreign inputs,
legacy rejection, normal/default no-ops, maximum revision changes versus true
no-ops, interval/deadline equality, a literal 0-to-1-to-2 revision trace, and the
same root action across scales. They assert contract properties and fixed
boundaries rather than recomputing expected financial answers with another
production calculator. Their eight migrated preconditions were separately read
and supply the intended complete initial/current Stage or a deliberate mismatch.

The time fixtures independently imply 5,000,000us query spacing and a
30,000,000us first deadline; the second eligible attempt counts as 2, while a
deadline observation leaves the prior count unchanged. Maximum-revision records
are supplied DTO boundary fixtures, not proof of reachable durable history.
The scale test rejects two supplied records sharing one action identity; it
does not establish global root ownership or prohibit a hidden second history.

This is not complete runtime coverage of every Stage/reference field, foreign
payload or reachable-history domain. The separate full-field independent
reference, hash/DTO bridge and all required boundary groups remain unrun gates.
None of these 29 definitions, their helpers or any target/reference validator
was imported, compiled or executed in this review. Only AST/data/Git operations
were used; no SQL, actors, PID/proc, network or CI actions occurred.

## Next gate and rollback

No static CODE blocker prevents root from separately authorizing a first normal
CI for the exact integrated source. Report actual new results separately and
retain every old source/run meaning. Independent numerical comparison must use
a separately reviewed v2 reference, without production validators/hash helpers
or selective field removal. Unit or CI success alone cannot close D2.

D2 remains BLOCKED: authoritative unique root history, approved immutable policy,
durable CAS/outbox, real cancellation/fill ACK, settlement, restart reconciliation,
admission/withdrawal/transfer integration and account restrictions are not supplied
by this module. It is USD-only, unconnected and has false activation flags.
Capacity, HA and real-funds production have no approval.

Rollback is confined to the fresh pure engineering deployment and its explicit
inventory version. Preserve historical V2/V3, old obligation/trade/journal facts
and original artifacts; do not initialize a new wait/action budget as rollback.
Returning to an operational V3 source requires the matching pre-pure-module
deployment, including removal of that module/tests; reverting ed81 alone returns
a historical candidate and its previous inventory gate, not an established
green deployment. Any later service rollback needs its own confirmed-effect
reconciliation.
