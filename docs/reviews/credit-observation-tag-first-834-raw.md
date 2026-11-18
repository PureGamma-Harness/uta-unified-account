# Independent RAW review of the first 834 credit-tag run

Decision: **PASS_LIMITED_PURE_ONLY**. The first source-bound run passed all six
selected methods with zero failures, errors or skips. This is a focused
in-memory credit-artifact/diagnostic compatibility result. Whole CI, financial
acceptance, native recovery and production remain unapproved.

Reviewed target source `834ad6e4da8a97c2246b0a49d82085183f73519c`, previously
CODE-closed in independent commit `33593fb0166f4f64b2a9d555d0090a150ed8bb4c`.
The first safe seal is `c8f795d7628576f9377e6ceebca2823f63d2ae87`; the final
owner seal is `1b7985679f8cd82df12668b28a2b4b0c9b3fcf05`, tree
`0363505947e6957b6c70e44d640b85e82b2f4ede`. Final explanatory changes leave
the target runtime, test, drivers, approved plan and historical old plan intact.

This was a read-only review after terminal sealing. The two authorized private
output scopes and owner files were not modified. The reviewer did not compile,
import or execute target source, rerun an artifact/test, open SQLite, inspect
a PID, send signals or perform native/network probes. A separate metadata reader
parsed JSON/base64 and compared bytes, hashes and Git blobs. It never executed
capsule content and did not copy the complete private capsule into public output.

All 14 public raw copies match their authorized originals and exact final-seal
Git blobs byte for byte, totaling 47549 bytes. Their original permissions are
0600. The raw manifest is 4126 bytes with SHA
`55f05fecec462b40ef3aab2154cdae5025839df8ec8442ab98a5f9b2fe87b6cd`.
The private immutable capsule is 1811575 bytes with SHA
`add36df8cf39fb7eedae90f8858d26101c25a69bb89dab6fc2e03e8862de13c1`.
Every one of its 65 decoded inputs matches the approved plan and exact 834 Git
blob, totaling 1342330 bytes. The current sealed physical inputs also match.
The capsule plan is byte-identical to the approved 14993-byte plan, SHA
`8f12dd7a2ad9faabf4981499dee4bf011111273a48bf797678053dbc684ee726`.
Its 61 UTA pins supply the independently injected full source-map expectation.

Original stderr contains each of the six approved method IDs once as `ok`, then
`Ran 6 tests in 0.269s` and `OK`. Original stdout contains exactly BEGIN and
END records; its END equals inner.execution.json, which also equals the inner
record in outer.execution.json. The pinned full-artifact method creates the
real current artifact, compares its complete source map with those 61 retained
pins, checks Enum tag/member/class-code identity and unchanged exclusions, then
calls the unchanged validator. The other methods retain unsupported-object and
code-constant rejection, Enum identity changes, provenance/type filtering and
original exception identity checks.

The returned whole artifact was not separately archived. Evidence for these
properties is the frozen method's assertions and its actual passing result,
not an independently inspected returned manifest. No artifact was recalculated
after the run to manufacture a missing archive. The plan counts 22 bounded
source groups; there is no separate per-group execution counter. Actual observed
method count is six. Its old non-executable limitations sentence saying twenty
remains documented without editing the frozen plan.

Runtime records agree with the approved plan: Python 3.12.14, exact executable
SHA `fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`,
affinity `[1]`, and isolated/no-site/no-bytecode flags. Inner before/after input
checks report equality across all 65 pins, forbidden-operation attempts are
empty and outer source/deadline drift is null. The reviewed guards and fixed
source support this in-memory scope; they are not an OS sandbox or a production
native-library attestation.

| Interval or termination | Retained observation |
| --- | --- |
| Inner loading and selected suite | 384510720 ns; unittest alone reports 0.269 s |
| Owned timeout host Popen-to-wait | 745755011 ns; actual exit 0 and reaped |
| Actual outer process observed by caller | 981377073 ns; actual exit 0 and reaped |
| Caller intent through completion | 982729829 ns |
| Pipe and publication state | Both EOFs, complete inner/outer END, TAIL late=false, outer status 0 |

The independent caller's launch/end times contain the complete host interval
and later TAIL publication in order. Intent preserves the actual timeout/taskset
argv and source/plan binding. The host has a twenty-second OS timeout; the
twenty-two-second parent interval is a completion/classification deadline.
The caller's actual exit/reap is present, so an earlier END is not used to infer
a future successful exit. This normal run provides no hard termination result
for blocked parent filesystem IO.

The collector reserved and wrote 11004 payload bytes. Its separately reserved
trailer used 143 bytes, giving 11147 total bytes: stdout 9654 and stderr 1493.
The shared ceiling is 262144 bytes including a 512-byte trailer reserve. Sticky
raw failure is false and both launcher streams are empty. Timeout, overflow and
short writes were not injected; those branches retain their static CODE-review
qualification rather than a fault-test PASS.

Key hashes are stdout
`d82769737c487a12ca231c1a78fd8dc9505ce7ca1914c2460dd3754010bb5429`,
stderr `a5f4892f290df958f1a9d055f210028d7e8210238619359497020c64baf86d3a`,
inner execution
`3d729a8e89cad95c1b48126f94218c90928f8437e6120f004e6fecfba5ed2bc5`
and independent caller execution
`2e579e8f0cee210f55f6a89cfff6c12526096f6bfce490a549d773446478e5bc`.
The companion JSON binds all fourteen originals and the inspected fields.

Preparation7030 and plan2e9 remain zero-attempt NOT_RUN, not RED. Prior review
cb875's original blockers remain historical text, followed by their 33593
closure and this distinct first-run result. PR42's first failed CI and missing
specific attribute remain unchanged; these methods do not retrospectively
classify every historical error. No rerun, SQL integration, financial activation,
native recovery, deployment, retry or real-funds permission follows. A separate
Draft fix PR can preserve this limited evidence without replacing the original
failed PR42 result.
