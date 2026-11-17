# Independent review: loaded credit identity at 848274e

Decision: **changes requested for complete credit-engine identity**. Three pure
counterexamples retain identical complete artifacts while an actual loaded
financial path or captured value changes. This blocks use of this identity as a
complete prerequisite for future credit decision replay. It is not evidence of
an online borrowing bypass: the module is unwired and adds no database, lease,
activation or borrowing permission. `NATIVE_PREPARED` remains closed.

The reviewed artifact implementation, tests and documentation are exactly
`848274ee7f774cd5780efb694bfc3f088944d482`. Review changes are restricted to this
document and independent evidence. No implementation or original test/raw file
was edited. Compatibility with the later financial-source verifier was checked
separately at `a4d4facc3235a324afbc0fdb19635bf0bbc86a75`, whose artifact module is
byte-identical to the reviewed implementation. That worktree was created from
the committed source, without the parent's untracked files.

## Confirmed identity failures

| ID | Exact source boundary | Independent result | Required correction |
| --- | --- | --- | --- |
| CA01 | `uta/credit_artifact.py:31` fixed module list omits `market_cache`; `:145` skips imported classes | Patching `MarketDecodeCache.parse` changes the result for `{}` from `RiskInputError` to a synthetic result, while the source and entire artifact remain equal. The actual service invokes this method at `uta/service.py:397`. | Include the actual market decoder module and its required method identities. Review other transitively used modules/classes; hashing all source files does not identify their patched loaded code. |
| CA02 | `uta/credit_artifact.py:175` only visits module-level uppercase constants; `:146` collects class methods but no class static constants | Patching `Ledger._LIMIT` from `10**38` to `100` changes `DurableLedger._stored_units('100')` from `100` to `LedgerError`, while source and the entire artifact remain equal. This constant also controls `credit._value` at `uta/credit.py:134` and durable ledger verification/posting at `uta/storage.py:399`, `:431`, `:522`. | Describe actual financial class constants, including `Ledger._LIMIT`, without collecting per-instance balances, locks, nonces or caches. Unsupported static values must fail closed. |
| CA03 | `uta/credit_artifact.py:131` recognizes the repr exclusion by function name/free-variable names/unwrapped name | A non-stdlib replacement for `_borrow`, named `__repr__` with free variables `repr_running,user_function`, captures financial values `101` versus `202` in `repr_running`. Bytecode is equal and outputs differ, but complete artifacts are equal. | Verify the real standard dataclass repr wrapper code and its actual class repr collection context before excluding only its transient memo. An arbitrary function name or identically named closure is insufficient. Retain all other closure values or reject them. |

CA01 and CA02 are in `probe-raw.txt`; CA03 is in `repr-raw.txt`. Both programs
deliberately exit **1**, preserving the identity failures rather than presenting
them as green acceptance tests. These are controlled loaded-code mutations in
the trusted Python process, matching the module's existing mutation-test scope.
They do not establish a remote attacker, an exploitable HTTP route, a successful
loan, or permission to alter a trusted deployment.

For a CA03 correction, authenticating wrapper bytecode alone should not
implicitly authorize the exclusion at a financial method collection path.
Only the actual local dataclass `__repr__` path should receive that exception;
recursive static function serialization should not inherit it. This is a
correction prerequisite, not a fourth independently executed counterexample.

## Confirmed positive boundaries

Static inspection confirms source hashes, loaded function bytecode, nested code
constants, defaults, keyword defaults, ordinary function closures, unwrapped
functions and supported module constants are separate inputs. This is more
than source-only identification, but the three omissions above prevent the
broader completeness conclusion. Parent-owned tests cover several ordinary
mutation cases; they were inspected and were not rerun as independent evidence.

The independent parser probe confirmed unknown retained fields produce typed
`credit_artifact_invalid` with **zero imports**. Four malformed inputs (invalid
JSON, duplicate key, `NaN`, floating metadata) each produced that typed error.
The parser does not read retained paths, compile code, call retained symbols or
choose imports from retained data. `assert_current_credit_artifact` constructs
the current engine from a fixed compiled module list, rather than importing an
archive-provided name. No parser/code-execution blocker was found in this scope.

The later native preflight (`26f7c59`, integrated as `691cc48`) is compatible:
one pure construction at `a4d4fac` completed, included
`uta.credit_native._verify_financial_source`, and reported 858 loaded functions,
100 constants and `activation_permission=false`. The new readonly adapters and
nested verifier class did not cause `unsupported loaded financial constant`
or closure errors. No preflight, verifier, SQL, loan or replay was executed by
that compatibility check.

`_LIVE_GLOBALS` excludes connection registries, locks and context variables by
an explicit compiled list. The parser checks that exclusion contract. Those
mutable secret-bearing objects should remain excluded; the corrections must
not serialize live nonces to close CA01/CA02. The artifact remains unsigned
evidence under an immutable-source/trusted-process assumption, not OS
attestation, a signature, or an activation capability.

## Reproduction, resource window and release boundary

Run the two evidence programs from the exact reviewed source, using a separate
exact compatibility worktree at the SHA above:

```sh
taskset -c 4 timeout 5s python3 evidence/reviews/credit-artifact-848274e/probe.py /workspace/uta-credit-artifact-native-compat
taskset -c 4 timeout 2s python3 evidence/reviews/credit-artifact-848274e/repr-probe.py
```

The first actual window was 2026-11-17 11:53:06.862754 through
11:53:07.490094 UTC (0.627346485s); the second was 11:53:52.450413 through
11:53:52.576719 UTC (0.126303734s). Combined measured pure probe time was
**0.753650219s**, below the parent's 5-second budget. There was no SQL,
database, listener, service, pressure test, external endpoint, live path or
original raw modification. Monkeypatch contexts restored process-local values;
the sole child process exited and no background work was created.

This review does not grant a release, funding or production approval. Keep
credit activation and new managed borrowing disabled until the actual complete
operation evidence, authorization, native constraints and independent replay
are implemented and accepted. This evidence-only review has no deployment or
data migration; reverting its files affects no runtime behavior. A fix to the
artifact format/identity requires its own source commit and new raw evidence;
do not overwrite these original failures.
