# M05 preview a365f37: independent CODE review

The planned once-push M05 control checkout has the nine selected tests and their reviewed dependencies. A separate manual-dispatch draft omits a YAML file those tests require. No new combined suite, build, marker, ref, push, SQL, crypto, native or financial workload was run by this review. The preview remains non-executable.

Fixed preview is `a365f37e23e1c0ce75e403062344a5f482c9a3cf`, parent `ed929d38648486ec01a01094b772b2c9c1072573`. Controller SHA256 is `eb447cefe07a04de9dbcf06b370834f4abf3f56a7ef5325313fe44403657d918`. The read-only Git/AST reader and its first output are in `evidence/reviews/m05-a365-code-independent/`. The reader imports no controller or test module; its exit 0 denotes successful metadata extraction, not test acceptance.

## Concrete dependency finding

In `.github/workflows/independent-m0.yml`, the control sparse checkout contains only `.github/workflows/independent-m0.yml`, omitting `.github/workflows/independent-m0-once.yml`. `tests/test_independent_m0_checkout_ref.py` explicitly reads both files in `CheckoutRefContract.workflows()`. The controller test also directly reads the once YAML. Dispatch's existing discovery command selects these tests, so that sparse tree cannot supply all required files. This is static evidence; no failed test was executed or invented.

The actual planned once workflow includes both YAMLs, all nine M0 tests, controller, escrow, cold-import helper, public certificate and public metadata. Its dependency set has no missing path in this review. The manual draft defect predates this preview's final integration; it does not establish a defect in the planned M05 once path or explain any old actual failure. A minimal additional sparse line, or an explicit unqualified-manual scope, requires a separate root/author decision. This OWN does not change the original a365 source.

## Source and authorization boundaries

Relative to FS tip `3cc254db...`, controller bytes change only the two APPROVED_BRANCH / REGISTRATION_ID constants from spent 04 to 05. All 61 top-level function/class ASTs are equal. The independent single-use proof closure is `837bd0ac8c43550590d8637000dea18db746d3ff`; a365's original policy still says that review is pending, and that original policy is not rewritten here.

The strict format-2 template has exactly 19 fields and `execution_authorized=false`; its control commit is zero and workspace reference is an expired placeholder. Outer policy has `next_run_permitted=false`, `all_component_CODE_reviews_closed=false`, combined PURE `NOT_RUN_REQUIRES_SEPARATE_ROOT_BUDGET`, and production/capacity/HA flags false. Its controller/workflow/escrow/certificate SHA bindings match the exact Git blobs. No actual `config/independent-m0-approved.json` exists in the preview tree or in marker-path changes since source909. Source history includes safe M04 evidence without merging the actual authorized M04 child merely to obtain documentation.

The control `uta` subtree is `4a0d5a989f0d7112454e41bbdb0162ffef34dbe4`, exactly the delivered ff814 and base6010 subtree. The separately checked-out financial workload remains exact `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`, tree `cee60bc0b5413551030300e065d0dcaac6a7ff55`, 5,518 tracked blobs. Both workflow workload steps select that full 40-character SHA. Neither control6010 runtime nor later tests replace the frozen909 financial workload.

Both argv templates and budget objects equal the existing false04 template: B then P, 10 seconds / 20 arrivals per second / 100 accounts / two shards / one allowed CPU, no cache or financial batch optimization, P only adds profile. The 3-attempt / 50 ms resource policy, 56+2+2 case outer budget, separate escrow budget, 64/96/32 MiB compartments and 2 GiB additional free space remain component code. Four authenticated closed-stream retention, private keys/DB/request exclusions, first UNKNOWN stopping P and original failure preservation retain their previous scope; they are not newly exercised here.

## Required next gates, not permissions

Root must integrate the independent component closure and resolve or explicitly scope the dispatch dependency before calling both workflow paths complete. A new immutable combined source needs its own authorized test run and complete first output. Source inspection predicts six guarded Python cold-import child launches; this is not a zero-process suite and does not authorize SQL/native/crypto capability tests.

Only after independent review of that actual new combined result can root prepare a final C and fresh workspace/reference checks, then a local M whose sole parent is C and sole added path is the strict approval marker. The actual M, source/code/workflow hashes, first-new-ref/attempt1 conditions, budget and recipient bindings require independent read-only review before root's separate final push decision. Any ambiguous response requires read-only reconciliation, not replaying a push or recreating a spent registration.

Spent01–04 stay spent. There is no durable external spent-token registry or global RNG uniqueness proof, and CMS recipient encryption alone does not authenticate the sender. M05 is diagnostic R&D and cannot establish exchange production readiness, 10k/s sustained capacity, replication or real-money approval. This review adds only evidence/docs; reverting it changes no service, account state or schema and must preserve all original failure artifacts.
