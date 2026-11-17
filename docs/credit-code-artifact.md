# Credit code identity, before an executable credit audit

The initial implementation's completeness claim was blocked by independent
review. The three original red counterexamples remain in
`docs/credit-artifact-848274e-independent-review.md`; the corrective slice and
its limits are recorded below. The original 12 green tests were insufficient.

This M3 component is synthetic, default disabled and unwired. It grants no
database permission, writer ownership, account authority or trading capability.
`NATIVE_PREPARED` remains unable to activate or borrow. The existing managed
new-borrow rejection remains in force.

`uta.credit_artifact.credit_code_artifact()` records a content-addressed identity
for the actual deployed source, actual loaded Python functions, unwrapped
functions, defaults, keyword defaults, closure values and compiled uppercase
module constants. The fixed compiled module list includes credit, its native SQL
definitions, writer fencing, ledger, risk, durable dispatch and API/signing code.
Python, SQLite and OpenSSL versions are explicit inputs. A source-only hash would
miss a patched `_borrow`, changed default or equal wrapper bytecode with a
different captured value; the tests exercise those cases.

The manifest contains hashes of code and constants. Live connection registries,
lease nonces, process locks and context variables are explicitly excluded. The
standard dataclass repr recursion memo is excluded, while its actual wrapper
and user function are retained. Unsupported closure types fail with
`credit_artifact_unavailable`, without invoking their repr or other custom hooks.
Artifact construction assumes immutable deployment files and a trusted OS and
Python process. It does not attest the OS or prove all possible runtime state.

`credit_artifact_id()` validates the complete format and returns
`credit-artifact:<sha256>`. `parse_credit_artifact()` requires canonical JSON,
the supplied content identity, bounded text and complete source/function maps.
Duplicate keys, floating metadata, nonstandard numbers, unsafe source paths and
unknown fields are rejected. The reader never imports or executes names or code
from an archive. `assert_current_credit_artifact()` compares retained data with
the current real engine; differing source, loaded code or runtime fails with
`credit_replay_engine_mismatch`.

This is one input to a future `CREDIT_BORROWED` decision record. It does not yet
capture or replay the borrowing operation, limits, pool source, debt, budget,
market, risk, journal or account transition. A matching artifact is neither a
signature nor permission: `signed` and `activation_permission` are always false.
No native obligation, dispatcher, route or successful financial path is added
by this commit. Full operation evidence and independent financial replay remain
blocking work.

## Validation and retained failures

Twelve tests cover real loaded-code/default/closure/constant mutations, source
changes, absent native source, excluded live secrets, unsafe archive content and
strict identity handling. The first build failed closed on a standard dataclass
builtin default factory; that raw failure is retained. The implementation now
describes builtin symbol identity without executing the builtin.

Raw output and exact source hashes are in
`evidence/runs/credit-artifact-initial/manifest.json`. CPU3 sequential tests passed
on Python 3.12 (12 tests, 0.539s) and Python 3.13 (12 tests, 0.604s), both with
ResourceWarning promoted to an error. The original first successful 3.12 output
is also retained. These are cohosted pure correctness tests, with no database,
listener, service, trading or throughput measurement.

Reproduce from the reviewed source:

```sh
python3 -W error::ResourceWarning -m unittest tests.test_credit_artifact -v
```

## Deployment and rollback

This slice has no deployment command, schema migration, CLI flag or activation
route. Shipping its files alone changes no existing borrower or ledger behavior.
Rollback consists of reverting this isolated module, tests and documentation
before another component depends on its artifact format. Once future credit
decisions retain these identities, retain the matching immutable build for
replay; do not substitute current code or silently recompute an old identity.
No real-funds readiness or production approval is asserted.

## Independent counterexamples and corrective slice

Independent review `1950f60e8bcc6ab7cde56676aa2b368b96eb4628` established three
real source-unchanged, full-artifact-equal counterexamples against `848274e`:
patching actual `MarketDecodeCache.parse`, changing `Ledger._LIMIT`, and using
an ordinary financial closure with the same name/freevars as a repr wrapper.
Their original exit1 raw output is retained; none is described as an online
borrowing or PREPARED activation vulnerability.

The fixed compiled dependency list now includes the market decoder and actual
risk/scenario, matching, lifecycle and dispatch dependencies. Loaded methods of
the market decoder are explicitly required. Uppercase static class variables
are read from raw class dictionaries and hashed, including `Ledger._LIMIT`.
Known exact `Fraction` and compiled immutable `_Scenario` constants are
described without invoking arbitrary dataclass/repr hooks. This remains a fixed
reviewed dependency list: future financial dependencies must extend and review
the list before a new decision format uses them. The separately unwired
`credit_transition` component is not used by this release's borrowing engine;
its future audit consumer must include its loaded identity.

The repr memo exception now requires the actual CodeType generated by this
runtime's standard dataclass decorator, the actual locally defined dataclass
owner and its actual `__repr__` member binding. This actual wrapper CodeType is
also fingerprinted. Similar names/freevars and even a real stdlib repr wrapper
assigned to `_borrow` do not receive an exclusion. New tests verify those
negative cases and the legitimate nonfinancial dataclass repr memo exception.
Unsupported loaded code constants are mapped to a typed credit artifact error.

All development outcomes remain in `evidence/runs/credit-artifact-peer-fix/`.
An expanded scan first rejected previously unsupported scenario constants; its
tool output is retained as an explicitly labeled transcription. Python 3.13
then rejected use of a removed private dataclasses helper, so the implementation
now obtains wrapper identity through a real dataclass template on each runtime.
A later test failed in `mock.patch` cleanup of the special function `__code__`
descriptor; the test now restores it explicitly in `finally`. Both original
failed subprocess logs and the source hashes are retained.

Final unchanged source passed 18 artifact tests and 11 accounting component
tests per runtime on Python 3.12 (1.703s), 3.10 (1.662s), and 3.13 (1.556s).
The corresponding process times, exact commands, raw hashes and source hashes
are in `final-explicit-restore/manifest.json`. All runs promote ResourceWarning
to an error. These cohosted CPU3 correctness results include one synthetic
temporary preseal database per runtime and no listener/service/load. Independent
review of the corrective source is required before its scope can be accepted.
