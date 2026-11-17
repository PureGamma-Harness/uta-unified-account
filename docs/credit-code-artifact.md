# Credit code identity, before an executable credit audit

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
