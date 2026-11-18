# Independent delta review: complete compared metadata

**CROSS-ENUM-ENTRY-001 CODE CLOSED at
`62ada25fbc4cb4f74f8615cabc11d7a890035ef3`.** This closes only the finite
metadata archive blocker from independent review
`d1c7551a54483bb733139f3a6d549bdbc29f7c32`. It grants no execution permission.
Target import/compile/test/SQL/native/process/PID/CI/child attempts remain zero;
external capture is still OPEN and production remains NO_GO.

Reviewed tree `aaee55cca891053905342132e97e9e4de7ccd2b7`, sole parent
`4ac29b30bfa69b2971a57d7ae2b70e287a607d72`. Older536 review2ce623c8 and
4ac29 blocker report are preserved; this follow-up does not rewrite their
historical source, plan or NOT_RUN state.

`check()` now saves expected_metadata for rule_id, rule_version, catalog_version,
market_version and market_id together with independently expected financial
values before the candidate call. After the call it records all five actual
attributes without string conversion, before any assertion. The metadata
assertion directly compares the two archived maps. The already-reviewed
CountedResult retains that same active record for ordinary/subtest failures.

The previous static counterexample is now represented: correct amounts but
catalog_version8 instead of7 records expected7/actual8 before failing, and an
incorrect market_id is also retained. This is source reasoning, not an executed
mutation test or observed failure. If the candidate/attribute extraction fails
before all outputs exist, the partial-stage semantics remain; the entry must
not call a partial record complete. The last method still asserts only its USD
quote and does not claim a metadata comparison that it never performs.

AST checks establish expected metadata precedes the candidate call, actual
metadata precedes the first assertion, all five keys are fixed, and comparison
operands are precisely the archived maps. The exact input constructor, fixture
models, independent Fraction valuation/enumeration and512 generator are
AST-identical to4ac29. All62 UTA Python files and the retained entry are
byte-identical; five selectors,512/6/8/8/4=538 counts, module order, runtime pins
and resource proposal are unchanged. The finite individual-quote and distinct-
input limitations in the prior reports still apply.

All67 canonical regular physical input files match their plan lengths/SHA256
and Git objects:1,354,752 bytes. Source worktree was clean. The new plan SHA256 is
`f51c0f682c24febadfac5f8bb6338d26752e0bd90877843fee34f75a4efea255`.
The entry remains12,343 bytes, SHA256
`898b1e9bfde80a7c970655cf8834324df9c781fb393ba66fde3c6226dedda77a`.
The separately checked `pure-once-plan-4ac29-NOT_RUN.json` is exactly the old
Git plan:11,958 bytes, SHA256
`7d994d5af9eda705644ac0fa81ba1b4568fd917d778224a5437c60b0fb139bb3`.
The original536 CODE-plan also remains byte-identical. No target source was
modified by this reviewer; checks used Git/text/bytes/stdlib AST only.

External raw/control/resource/Git capture and actual exit/wait/reap/EOF still
require their own CODE review and unique root GO. The entry's END or outcome
receipt cannot prove its later process exit. No test result, vector completion,
latency, sandbox, admission or production acceptance is claimed here. Full
Cross, joint borrowing/concurrent reservation safety, matching, capacity,
real funds, insurance and ADL remain outside this pure slice and NO_GO.

No deployment or data migration occurred. Rollback removes only test/control
changes while preserving both old plans and first results; parent runtime and
default service stay unchanged. No main-worktree/index operation was performed
during this delta review.
