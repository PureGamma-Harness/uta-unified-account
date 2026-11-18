# Independent review: exact versioned AST allowance

Decision: PASS_STATIC_NO_BLOCKER for
fadd182da051ee84681f1c77734543d33751e3e5, exact parent
8faa56d5fcfcd1b176cbb1c2d8e142986f56ab15. This is an exact versioned allowance
for one previously reviewed ordinary test method. It does not disable the
complete-module guard or change the original reference. A separate new first
normal CI is appropriate for root to decide. This review is not a CI result.

The four changed Git blobs match author-worktree bytes. UTA, the durable-fault
test module and native SH fixture have zero diff from the parent. The original
387-byte original-ast.json is unchanged, SHA-256
52fd579fcc903f9590da7dc9d3232e09e48bbca1e0fcc96a48587051b7339922.
Only source/Git/JSON and AST data operations ran; no target or financial import,
target compilation, actual guard/test, SQL, process, native action or CI ran.

## Exact allowance and unchanged whole-module protection

The guard hardcodes exactly the partial-publication method name, requires one
matching ordinary method, and checks its current AST against the reviewed
version before replacing anything. The checked-in delta has an exact field
set, native schema version and fixed original-reference path. It supplies one
previous function, whose node type, name and AST hash are checked. Restoration
affects only that method node, in memory, before the unchanged final whole-module
comparison. No restored source, AST or bytecode is executed by this path.
There is no wildcard exclusion, class-wide allowance or alternate recovery hash.

Independent data checks reproduce:

- Current method AST: 086bfd15b452dbfe134da509fb1ff2bf1fc45ae82b857edef38ba9ea37007e8e,
  identical to the reviewed 8faa method.
- Previous method AST: 860dbe3535fd7305fd8ae64307c71c446468ab55bf63a122411998988c839907,
  identical to that method in both 72dd and frozen 5a source.
- Restoring only that node makes the complete instrumented module AST identical
  to 72dd. The approved method is the sole structural difference being allowed.
- Frozen 5a source SHA-256 389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6
  and its canonical whole-module AST
  6158b76f0c38eb9aa7acf7a4c28c88357cb3223a0f875bcb63f2db08b513b1d6
  agree with the untouched reference file.
- Putting only the reviewed current method into that frozen data tree yields
  0b20c601d3d20df91537154703257db3258ad58feec0bf286735d927ce7d9fdc,
  explaining the changed normalized-module reference without accepting it as a
  new whole-module golden value.

The old guard's entire scheduling/NativeSH/failure-hook normalization prefix and
its final full-module assertion retain identical ASTs. All other recovery,
financial assertion and cleanup nodes remain subject to that final comparison.
The native pure module's AST is identical to its parent; its change is comments
only. The extracted canonical/ast_sha helpers are unchanged. The guard adds only
locals and uses the extractor's existing ast/json/hashlib/ROOT/METHOD/builtins
dependencies; it requires no new unprovided global helper or financial module.

## Negative definitions and evidence limits

The new pure method first checks canonical AST equality across unparse/parse,
then appends Pass to the approved ordinary method or the protected recovery
method. It patches only reads of the durable-fault source path; reference/delta
JSON reads fall back to the saved original reader. The actual complete guard is
called inside assertRaises(AssertionError), rather than a duplicated acceptance
predicate. Synchronous per-subcase invocation avoids a deferred closure issue.

Independent AST data operations confirm exact round-trip equality and changed
method hashes for both mutations. An ordinary mutation must fail the exact new
method hash before restoration. A recovery mutation is retained by the unchanged
normalization and must fail the final whole-module hash. These are static paths
and hash witnesses; neither the new negative test nor the actual guard was run.
Cross-interpreter behavior remains a new CI obligation.

The delivery document preserves the earlier failed jobs and separates their raw
observations from this candidate. Historical counts and old/new method passes
were supplied by root's fixed CI collection; they were not recollected here.
No native horizon, capacity, HA or production conclusion follows from this AST
compatibility repair. The already reviewed pending-order test behavior still
runs as its current source; the restored old method exists only as guard data.

Rollback reverts these four test/reference/docs changes and preserves the old
reference, original failures and approved compatibility review. No financial
schema, authority, migration, product, lease or timeout changes. Any future
allowance change remains a separate versioned source/data diff for review.
