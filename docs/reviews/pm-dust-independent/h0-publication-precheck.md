# H0 source912: limited publication/history precheck

This is a **privacy and delivery-scope precheck of one immutable Git range**,
not a security audit or H0 acceptance. Publication remains root's decision.
No push, PR, merge, product import, SQL, new dynamic test or private authority
read was performed by this check.

The inspected range is
`909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0..912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a`:
13 linear commits, 97 changed paths, 100 distinct path/blob versions and831,755
bytes read directly through Git. Forty-nine JSON blob versions were parsed.
Nothing was materialized from the5,614-file candidate, and no external key,
database, signed request, nonce record, TLS file or original private stream was
opened. Existing frozen sources and running jobs were untouched.

[The checker](check_h0_public_range.py) and [final result](h0-public-range-v2.json)
retain every inspected blob identity and SHA256. Defined common private-key,
token and signed-URL patterns had no matches; no DB/WAL/SHM/key/certificate
artifact path or JSON string under the selected secret/nonce/signature/body
field names was found. This does **not** prove that arbitrary encoded or
unrecognized sensitive information is absent. Files containing public schema,
runtime generation of random test keys, metadata hashes and pointers to private
originals remain source/document evidence, not copies of the private originals.

The initial checker/result are retained separately. Its signed-URL pattern
covered a recognized token parameter after another query argument, but omitted
the first-query-argument form. The revised pattern covers both forms, and the
same100 blob versions were read again. Both result manifests retain identical
source/blob inputs and zero flags. No first result or source history was
overwritten, and this is not represented as a new product test.

## Verified scope boundaries

Only three runtime files differ from909: new `credit_auth_h0.py`, new
`credit_auth_h0_schema.py`, and the shared `request_signing.py` refactor. The
checker independently parses the H0 source AST: the constructor defaults
`enabled=False`, requires literal `True`, and otherwise raises
`credit_auth_disabled`/501. The three recorded observation permissions are
literal false: `financial_authorized`, `source_delivery_authorized`, and
`execution_authorized`.

The observation object is locally issued only after the real AuthDB COMMIT
returns. Inspection is a process/thread-local lookup of a passive observation;
it is not a financial source, inbox, execution or lending capability. This
static assessment does not validate every runtime permission or race path.

The public ingress, CLI, credit dispatcher/policy/native-v2, writer fence, API,
server and service files are byte-identical to909. Existing managed new-borrow
refusals remain in `credit.py`; H0's parsed `/v2/.../borrow` request target is an
internal authentication observation shape, not a newly wired public route.
No HMAC3 source, financial executor, public borrowing enablement, READY
transition, migration or listener is supplied by this candidate. Source/test
code that creates fresh random private fixtures must not be described as a
public raw-key or request artifact.

## Draft wording and evidence limits

The frozen candidate's historical author evidence remains its own22-component
observations and earlier retained failures; it is not relabelled with later
validation. The integration lead reports three later source912 full unit
reports, each1,823 tests with no failures/errors/skips and359 matching inputs,
but an exec-server disconnect lost the attached outer controller's final
recording. The third outer outcome and aggregate matrix report are absent;
the recording state remains **UNKNOWN/incomplete**. Do not call the whole
controller a natural PASS. This privacy check did not reopen those external
original files or repeat their validation.

The integration lead also reports four independently executed P1 races, each
one actual bounded schedule. Their narrow result must remain distinguished
from exhaustive interleavings, default quota coverage, real process reply loss,
H0's entire compatibility matrix and any H1 financial-source bridge. These
later results live outside this exact candidate range; this report neither
independently verifies them nor grants their scope to source912 automatically.

The source preserves original payload/revocation/profile-association RED
histories and their fixes. Public Draft wording should link the actual source,
those first failures, later independent evidence and the controller-recording
limitation. Full H0 release, new-source CI/package qualification, HA/antirollback,
capacity and real-funds production approval are not established here.

No privacy-blocking artifact was identified by the defined checks on this exact
range. Root may consider publication as a **default-off, auth-only Draft** with
these limits intact. This statement is not an approval to deploy, merge, enable
new borrowing or represent production readiness.

Deployment/rollback of this report changes no runtime or data. Existing
accepted AuthDB identities, audit history and business CIDs must remain
preserved; deleting or downgrading authorities is not a rollback procedure.
