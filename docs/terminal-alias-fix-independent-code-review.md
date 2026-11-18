# Independent code closure of terminal birth and watermark aliases

**PASS for closure of the two recorded aliases in the valid finite JSON
domain.** Reviewed delivery `56d2c6cee7cde1b2f74cf2c959cfed07044981f0`, core
`4f9efc9e16da108fabe3be0eaec4d9f922dad948`. This is code/AST and retained-
evidence review only: no project function, fixture import, new test, live
directory, SQL, observer, audit, signal or service was executed. All candidate,
financial, replay, production and capacity flags remain false.

## Closure and policy

Birth validation now requires positive, bounded ASCII decimal text whose
spelling equals `str(int(value))`. Consequently `2` and `02` cannot both be
accepted identities, while the existing pairwise `(pid,birth)` comparison still
allows the same PID with genuinely different accepted births such as `2` and
`3`. Boolean, empty, non-ASCII decimal, zero, leading-zero and overlong tokens
are outside that rule. This canonical spelling is an explicit new system
policy, not a claim that the fixed 909 source or this review established the
kernel's representation behavior.

Each financial watermark independently requires the complete exact field set,
format integer 2, two valid digests and positive exact-integer ledger/business
sequences. Reconciliation and finance projections must then pass
`strict_equal` over their whole structures. This closes the recorded float
ledger-sequence alias without a one-field special case. Checkpoint/outer
watermark schemas are also explicit; missing and extra fields require a future
versioned contract rather than implicit acceptance.

`strict_equal` first checks exact value types, then dictionary key sets, list
lengths and every corresponding child. It uses an explicit work list instead
of recursive calls. Thus int/float and bool/int values differ at any JSON
depth; null equals null, negative scalar values compare only to the same type
and value, and list order/length remain significant. Source-map, producer
projection/clock, before/after watermark, cold response/receipt and coverage
bindings use the same helper.

The domain matters: parsed JSON dictionaries have string keys and acyclic
containers, and the binder's preceding `numeric_tree_bounded` rejects nonfinite
or unsupported magnitudes. The helper is not an arbitrary Python-object
comparator; numeric/Boolean Python dictionary keys and cyclic objects are not
JSON inputs. Same-type float signed zeros compare as equal numeric values,
not as identical original spellings. Exact file-byte integrity continues to
come from the independently supplied manifest pins. This review does not
establish arbitrary-depth JSON decoder exception coverage or a hard I/O-time
bound; those are separate from the two aliases being closed.

## Evidence and scope of validation

Independent source/AST checks and hashes are retained in
[static-review-and-source-pins.json](../evidence/reviews/terminal-alias-fix-code/static-review-and-source-pins.json).
The delivery's binder bytes equal the frozen core. The author's driver SHA
and all four registered input SHAs match that core, including the original
three-case challenge source. The retained author output reports **14/14
cases passed**, exit 0, **214,873,239 ns**: 13 bundle cases and one group of five
direct recursive-comparison controls. All 13 bundle results preserve every
permission flag as false. This review inspected those original bytes; it did
not independently reexecute the cases or rerun the original 12/18 checks.

The earlier six-RED result, the original 18-case result and the additional
two-RED/one-PASS result are byte-identical to their earlier sealed sources.
The last retains its 7,301-byte stdout SHA256
`df90d11aeb52884cfc2aa81b33be83460e72469f2a75c6cdc3811d3717a5dbe7`.
No later result supersedes those source-specific failures.

These are metadata consistency checks. The child stdout hashes are pinned
declarations; filtered responses cannot reconstruct the original stream bytes.
Neither source review nor matching metadata proves financial authenticity,
fund conservation, actual process existence, six-hour completion, complete
business/risk replay, replication or HA. Actual terminal sealing still needs
the original supervisor's natural collection, an authenticated reviewed
manifest and a separate explicit operational authorization. The code keeps
`REVIEW_AUTHORIZED=False`.

There is no migration, public API change or operational activation. Retain
this narrow code review with the fixed source and original results. Revert
this evidence-only commit to withdraw the review; preserve all raw failures
and author output. Reverting the actual fix reopens the two recorded aliases
and does not authorize a fallback activation.
