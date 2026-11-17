# Independent recheck of the credit identity corrections

Decision: **CA01, CA02 and CA03 are closed for the exact corrected source
`fc63938018213a96de12ed5423842ec2e57ef746`**. This is a scoped identity component
review, not complete credit audit/replay, production, activation or real-funds
approval. The original `1950f60` review, three red counterexamples and failed
exit1 raw bytes remain unchanged.

No runtime files or original tests were changed by this review. A new independent
pure probe repeats the original mutation inputs and records actual before/after
complete artifact IDs, rather than relying on the implementation's added tests.

| Original block | Corrected source boundary | Independent actual result |
| --- | --- | --- |
| CA01: patched market decoder omitted | `uta/credit_artifact.py:36` includes `market_cache` and risk/scenario dependencies; `:43` requires the actual decoder method | The same `{}` input changes from `RiskInputError` to the same synthetic result under the original method replacement. Source remains equal, and the complete artifact ID now changes. The actual method is in the loaded map. |
| CA02: financial class bound omitted | `uta/credit_artifact.py:211` reads local classes' raw uppercase variables, without invoking descriptors | The original `Ledger._LIMIT=100` mutation still changes `_stored_units('100')` from `100` to `LedgerError`. Source remains equal, and the complete artifact ID now changes. `uta.ledger.Ledger._LIMIT` is in the constants map. |
| CA03: arbitrary repr-named financial closure excluded | `uta/credit_artifact.py:154` requires the actual standard wrapper CodeType; `:182` additionally requires the actual local dataclass repr binding | The exact original `repr_running={101}` versus `{202}` factory, identical bytecode/freevars and outputs `101` versus `202` now produces distinct complete artifact IDs with equal source. |

The additional real-wrapper controls also pass. Assigning the actual
`LoanAccount.__repr__` standard wrapper to `CreditService._borrow` does **not**
receive the exclusion; changing its memo changes the complete artifact ID.
Changing the same memo at its legitimate dataclass repr location leaves the
identity unchanged. This verifies both the standard code identity and the
collection binding, rather than trusting a function's name or free-variable
names. `_static` recursively serializes functions with the exclusion disabled;
the only enabling call is the explicitly checked class repr collection path.
`_DATACLASS_REPR_CODE` is itself a fingerprinted compiled constant.

The expanded dependency inventory constructed successfully with 1,255 loaded
functions and 163 constants. The independent probe explicitly checked the
market decoder, risk conversion, latest native full-source preflight and compiled
scenario collection. Known exact `Fraction` and `_Scenario` constants have
explicit serializers. Unsupported loaded values still fail closed. The
implementation's retained development failures, private-API compatibility work
and 29-case runtime matrices were inspected as supplied evidence; this review
did not rerun those matrices or overwrite their output.

The live registry/nonces remain excluded: a synthetic nonce marker changes
neither the artifact nor its serialized text. Unknown archived fields produced
typed `credit_artifact_invalid` with zero imports; invalid JSON, duplicate keys,
`NaN` and floating metadata each retained that typed rejection. Retained archive
data still selects no source file, symbol, import or executable code.

## Exact evidence and remaining boundaries

The new raw output and runnable independent probe are under
`evidence/reviews/credit-artifact-fc63938/`. The sole CPU4 window was
2026-11-17 12:02:14.504577 through 12:02:15.293999 UTC, measured
**0.789423196 seconds**, exit0, with ResourceWarning promoted to an error.
There was no SQL, database, listener, service, pressure test, old long-job path
or background process. Patch contexts and `finally` blocks restore local
bindings/memos. The manifest hashes the corrected source and all original
review bytes, and checks those original files against `1950f60`.

```sh
taskset -c 4 timeout 5s python3 -W error::ResourceWarning evidence/reviews/credit-artifact-fc63938/probe.py
```

The dependency list remains fixed and reviewed; this is not a proof that future
dependencies or arbitrary Python runtime state are automatically covered.
Future financial paths must extend their identity contract explicitly. The
unwired `credit_transition` component remains outside the current borrowed
operation's identity list and must be incorporated before a future audit uses
it. No current borrow, native, writer, service or durable dispatch source imports
this new identity module or transition component. Artifact flags remain
`signed=false` and `activation_permission=false`; no lease, SQL constraint,
dispatcher, HMAC permission, managed borrowing success or activation was added
by this review or by the scoped identity fix.

Full operation evidence, first-source provenance, native obligations, persistent
FIFO admission and independent financial replay remain separate acceptance
requirements. `NATIVE_PREPARED` stays closed. This review adds only evidence and
documentation; it has no deployment, migration or runtime rollback action.
