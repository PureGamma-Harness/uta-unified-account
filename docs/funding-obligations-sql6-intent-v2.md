# SQL6 exact-intent metadata correction: CODE proposal

This is a separate CODE-only scope based on
`9171e8e5e8d16b99a8a46f2f6ec1563754f55811`. No target import, bytecode
compilation, SQL, thread, worker, signal or new test execution is authorized.
The original first execution remains external caller126 / FIRST UNKNOWN,
SAFE`caea35102e0d4c77ca348597da429bbabafda106`, independently preserved by
RAW`b5fbbf464b3e436d87d7e09ea848e0aee2ad7ecf`. The16 caller checks and17 target
argv items are different counts; fifteen checks passed and outer_intent failed.
All46 originals and the old source/plan/evidence namespaces remain untouched.

## Concrete correction

The actual runtime bootstrap raw literal starts with LF. The old metadata
generator removed that LF while splitting source text. The unchanged strict
caller correctly rejected a1875-byte actual string versus a1874-byte template.
Only metadata construction is corrected. There is no strip, normalization,
fallback, relaxed equality or retrospective repair of the first UNKNOWN.

The new standalone static preparation/check tool uses Python AST parsing only.
It never imports or executes the target, generates target bytecode, or calls
eval/exec. It requires a single top-level BOOTSTRAP assignment to a string
Constant and reads the complete literal value. It also requires a single
17-item command List in the original run function. Literal strings are retained
exactly; every dynamic AST node must match a fixed whitelist for the executable,
BOOTSTRAP, capsule path/hash, approved plan SHA, source HEAD and inner path. Any
unrecognized expression, extra assignment, reordered item or changed argument
fails static validation. The resulting full17-item template is compared by exact
list equality with metadata; the first LF is explicitly required.

The complete future caller argv is separately compared with a fixed literal
construction and two new namespaces:

- `/workspace/uta-funding-obligations-sql6-intent-v2-once01`
- `/workspace/uta-funding-obligations-sql6-intent-v2-host-once01`

All checks occur in memory before preparation writes any new plan. Old9171
plan/caller-plan/freeze metadata are copied byte-for-byte from Git to
`sql6-9171-FIRST_UNKNOWN/`. Current target/caller plans then receive distinct
scope/source identities and the exact bootstrap. Historical UNKNOWN references
and old hashes are retained. Static checks may inspect public source/metadata
and run bounded Git reads; they do not touch DBs, capsules, birth records or
other old private originals. The static tool is not a financial runtime entry.

## Fixed scope, pins and qualification

All69 original target input files remain byte-identical to9171, including64 UTA
modules, the original six-test fixture, independent oracle, manual oracle and
original entry contract. The runtime caller is also byte-identical. The new
static tool and this document have separate preparation-control pins and do not
become extra target-loaded inputs. The new plan metadata itself is separate
from the69-file map. Static preparation and later CODE review do not imply that
those preparation controls were loaded into a running financial process.

Unchanged proposals: exact six ordered methods; nine fresh synthetic DBs; exactly
two competition test threads with maxlive2; no workers/network; CPU1; target45s
plus5s drain/classification; global caller75s plus failure wait2s/drain.2s; shared
target raw256KiB including512-byte trailer; caller raw1024 bytes including512;
per-file4MiB; observed logical DB64MiB/45 files and control8MiB, without a native
aggregate hard-quota claim. All selector, thread, orphan REVIEW, read-only reopen,
native-close observation and first-failure policies remain the original scope.

The static proof reports exact17-item target equality, complete caller equality,
1875-byte bootstrap hash, retained first LF and unchanged69 inputs. A standalone
`--check` also verifies actual physical/Git source, plan bytes, original caller
bytes and separately pinned preparation controls. It does not run targets or
grant execution. No execution plan is produced when static validation fails.

Only after independent limited CODE review and a separate root GO may the new
literal invocation be launched once. Any first FAIL/UNKNOWN remains preserved;
no retry-to-green or shared authority reuse. The root must observe the actual
future caller exit/EOF separately. Financial/model/production limitations remain
unchanged: no cross-MM/insolvency, process-tree fault recovery, HA, production
scheduler, pending-funding order/withdrawal holds or capacity acceptance.

No schema migration or production activation is introduced. Rollback drops the
new unexecuted metadata scope, preserves the original UNKNOWN and every original
obligation/receipt/journal, and continues to forbid real-funds activation.
