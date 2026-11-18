# Independent admission replay delta closure

**Financial CODE_ONLY CLOSED for fresh-authority preparation** on source
`be3c5c3ad695caedf438e09a25461571855fc43d`, tree
`6bb1ff04c5efef04b09c8fa077b8a702ccbe528e`; metadata OWN is
`1b5845d2f46e4a25454cf7e1bf539afc418c4c6e`, tree
`f7df9ec658c9173e9a524b28cc56ce08a01336be`. This is not a test result,
bounded-entrypoint approval or execution GO. The reviewer performed only
Git/text/JSON/AST inspection, with no target import, compile, test, SQL, probe
or child agent.

The sole runtime delta adds `control_state_valid` before either admission
branch, requiring both captured halt values to have exact native bool type.
RO with actual True remains allowed; None, unknown text, integer0/1, list and
dict values now make the combined checks fail even when both snapshots carry
the same malformed value. Removing this one statement reproduces the entire
prior decision_audit AST. All other UTA files, including financial admission,
capture and existing_services reconstruction, remain byte-identical to90ba.
This closes `ADMISSION-RO-HALT-SHAPE-001` on this new source, while preserving
the original a9ac NOT_CLOSED report for8be/90ba unchanged.

The corrected pure class directly declares7 selected methods. Its new RO
positive/negative fixtures use isolated copies of the prior manual record,
and its new missing/unknown policy/evidence-contract checks reach the existing
UNSUPPORTED gates. The4 SQL methods use4 fresh authorities, one local fill and
no matcher. The added synthetic case first calls the real `_source_arguments`,
appends a content-addressed old-style policy on that new test authority, then
expects the exact StorageError and ambiguity cause with unchanged account
view. Required imports, globals and method descriptors are present; there is
no inherited TestCase expansion or selected-AST reconstruction. These are
static import/dispatch conclusions, not executed PASS results. Passive sqlite
library import is required by the pure module; actual connect/SQL remains
forbidden in its future runner.

Policy coexistence/read reopen and existing-authority writer migration remain
OPEN. Delivery now explicitly chooses fresh synthetic authorities only. The
negative `_source_arguments` fixture does not certify full open_existing_services
or successful migration. It leaves genuine ambiguity refusal, immutable old
policies, exact source/runtime binding and current policy/artifact checks
intact. No deduplication or compatible-math bypass was introduced.

All64 regular physical inputs,1,323,284 bytes, match manifest and frozen Git.
Manifest SHA-256 is
`649e85fe996a2a93e3e3c3548807bd1e83934f701ff4127d1c6e228caa7243e1`;
plan SHA-256 is
`0c5cbd76e4ed78590d85be6feacac71141fc7249a50b88cd302e6c8b6b53631f`.
The original90ba manifest and plan are retained byte-for-byte, with zero
attempts. Original a9ac review paths also match their Git bytes. The documented
sparse-merge FileNotFoundError was an administrative freeze failure before
execution; exact restored owned paths match current frozen Git. It is not a
target retry or a claim that restored inode/timestamps equal an executed run.

There is still no bounded once entrypoint. Root must separately review its
source binding, actual runtime, pure connect guards, raw cap, timeout and
actual exit/reap before a first7-method run; SQL needs separate authorization.
Numerical risk/reserve independence, historical freshness, lease/auth,
rejection archives, arbitrary concurrent partial-fill guarantees, migrated
authorities, performance, HA and production remain unaccepted.
