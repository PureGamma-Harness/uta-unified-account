# M0 regular-entry proof: fresh scope and single consumption

**CODE/PURE candidate; independent new-source review pending; overall NO_GO.**
Base `c52494bd8da14bfca26d21e498744b3888de94e4`, frozen code
`4f316a89da1a001a9670a41cfeca754e67de1401`.

## Original counterexamples remain retained

The original nonregular-disappearance batch remains at93060e8 with25 PASS/2 RED.
The c524 correction's author14-method PASS remains tied to controller SHA256
`f0795cdb4d5992eeaa744f5088f7d476de773a1bb40d885f6bfcb6f80f9e33bb`.
Independent first review
`31b4af9996b4c2bfbfe58b1257b9f0519b328043` preserves20 groups/19 PASS/1 RED,
exit1,199808835ns. Its source-bound fixture SHA256 is
`92b641e46f941dfc51c1b7613d90ccfc1ebe2da07fafa7d5292289ff5427aee0`;
first stdout SHA256 is
`2806f86558ac9a222d753ed121bb46784d2e4d5e8484423f61e6b9e600065a5e`.

The remaining RED deliberately reuses the same FileNotFoundError object:
CASE_B's valid regular-entry lstat leaves a string attribute on it; ESCROW_B's
unknown-type query throws that same object and receives an incorrect retry.
This is an explicit metadata-hook counterexample, not observed kernel error
reuse or a diagnosed cause of actual M04. All original raw files remain intact.

## Revised internal contract

Each attempt inside `_fresh_resource_scan` creates a fresh opaque object in a
private ContextVar, and resets that context in `finally` on every return or
exception. Nested scans restore the outer context. The original start clock,
stable-path/type state and size lower bounds remain shared across the original
bounded attempts; a new proof token does not reset a deadline or budget.

Only a positively nofollow-regular enumerated entry, exact failing ENTRY_LSTAT
filename and active scan token can issue `(opaque token, exact path)` evidence.
`_known_missing_sqlite_aux` removes that evidence **before** checking errno,
path, role, current token or main/parents. The token must be the identical
current object and the path must match. Every handler read consumes evidence,
including a failed validation. Outside the scope, bare strings, foreign scan
tokens and already consumed proofs all reject. A missing main/parent does not
preserve a proof that could be restored and retried later.

New lstat, directory-enumeration and unknown-type metadata errors explicitly
remove any previous proof from the reused exception before classification.
Consequently an unused proof cannot be carried into a newer unknown metadata
observation in the same attempt. This is stronger than clearing only the
specific cross-phase string attribute from the first fixture.

Opaque objects are internal only. They are never printed, serialized, hashed
as a public identifier or added to D1 records; tests report boolean outcomes
instead. This mechanism is not a client financial permission. Existing D1
schema and strict public projection remain unchanged.

## One new-source execution, not a historical rerun

Source was committed first. The sole authorized batch ran2026-11-18T00:22:56Z:

```sh
taskset -c 1 timeout --signal=KILL 10s \
  python -B tests/test_independent_m0_scan_proof.py -v
```

Result:10 unittest methods PASS,0 failures/errors, exit0,0.012s unittest time.
The original source pin, input hashes, start, exit, stdout/stderr total1802B
under `evidence/independent-m0-scan-proof/pure-once01/`. Each output was capped
at40KiB. Input SHA256 was unchanged after the run. No retry-to-green occurred.

The new batch adapts only the original single RED's same-object CASE_B to
ESCROW_B sequence, retaining its first valid2B scan and requiring rejection of
the subsequent unknown hint. Additional own-file/fake controls cover one-use
consumption in the same scope, wrong path, unused evidence across scans, a new
unknown hint/lstat revoking unused evidence, out-of-scope/direct rejection,
parent-validation failure, success/error/KeyboardInterrupt context reset,
fresh nested scopes and outer-context restoration. The old14/20/27 batches
were not executed. No token values enter these raw records.

New controller SHA256:
`0e80c84030ca984a752d6991417a1454b02c64cb4be3fd4d50e97c1f4c7d87f2`.
New test SHA256:
`8cc1ceb30977434774dfb16fa974a7c1bbd0ae00c8c4308c6390d13ec89af49a`.

## Scope, deployment and rollback

Only the resource proof mechanism and its new narrow test change. The3-scan/
50ms admission/completion checks, entry/byte compartments, existing resource
tests, exact auxiliary regexes, business source909, `uta/`, workflows, approval
and namespace pins, crypto and escrow remain unchanged. No SQL, native worker,
owner, actual signal, CI, M05, ref/push, network, protected long process, key or
quarantine was touched. Standalone audit hooks reject those execution effects.

Same-type dev/ino replacement, metadata ABA, actual SQLite lifecycle,
performance, capacity and HA remain separate open gates. This scan proof does
not establish filesystem snapshot atomicity or kernel-call preemption. The
isolated SQL-probe WIP is a separate unexecuted worktree and is not part of
this candidate.

Artifact-group independent CODE review and root's later combined-pure source
acceptance remain required before integration can be called verified. No new
run/registration permission follows. Roll back code4f316a8 while preserving all
raw evidence; that restores c524's known proof-reuse gap and must remain NO_GO.
There is no financial/schema/customer-data migration or rollback.
