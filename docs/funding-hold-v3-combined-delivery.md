# Combined market control and independent funding verification

本页保留原组合源码的 CODE 冻结与部署边界。原 `7a4f41a6` 的首轮 push / PR 均已失败，实际摘要见 [首轮 CI 记录](funding-hold-v3-first-ci.md)；下文的待执行表述仅属于原冻结时点。后续参考契约修复、生成器变化和验证路径见 [参考契约与回归](funding-hold-reference-contract.md)。目标运行时、原保护测试、适配器和完整比较驱动未因该修复改变；原源码、审查与失败记录继续保留，不能移用为新候选通过证据。

This candidate combines reviewed market-control deliverye409db54 with pure
funding model16f64fec, finite readiness diagnosticsd128ee6e and independently
developed V3 verification. It is a new combined source; previous CI successes
are not substituted for its pending first workflow.

During recognized temporary publication barriers, SUBMIT remains PENDING without
an attempt or fabricated reservation. Complete persisted-state CAS rejects a
superseded phase's global rewrite. The funding model separately compares complete
expected stages/revisions, retains immutable consumed exposure/cap lineage and
does not increment unchanged wait records. These supplied USD calculations
remain unconnected to financial admission/payment; all activation flags are false.

The independent Fraction V3 source C7975266d/Fcab03a38 is exported as11 exact
files,168678B, with independent CODEe0d6b3b2. The target marshaller6f7a5a87 has
CODEabaa526c, deriving its nonfinancial framework from f8/35c5b22b. The complete
response drivercd583c1e has independent CODE6c777874. Each assessment is limited
static evidence. No generator, target, reference, validator or new test has run
for this combined source at this freeze.

The V3 driver defines1024 ordered unique synthetic cases,512 declared valid and
512 negative, through10 operations. Each request passes separately through
both implementations' loaders/evaluators. Comparison includes all typed response
fields, array order, identities and error classifications; unknown exceptions
remain technical failures. Declared valid cases cannot pass by matching rejects.
This is a correctness gate, with no open-loop capacity or duration claim.

Historical failures and blocked predecessors are retained. PR63's original
readiness failure remains UNDETERMINED. PR64's success did not produce failed
recovery diagnostic text. Old reference612 remains blocked; the new local
lineage rule69/54af is a forward policy clarification, not an external exchange
claim or a rewritten old result. Old V2 marshaller tests are framework regressions,
not proof of V3 model agreement.

The runtime contains66 Python files and the HTML asset. Only the three reviewed
market-control modules differ from public base27e9442d; the pure funding module
and other64 runtime files retain base bytes. The exact runtime/verification pins
are recorded in evidence/integrations/funding-hold-v3/combined-manifest.json.
Literal inventory V4 remains66 Python files. No new product, mode, order type or
financial permission is enabled by the verification code. Unsupported APPLIED,
real ACK/outbox, durable global action ownership, source-content authentication
and new hold integration remain blocked. Existing product/mode rejection
boundaries remain those of the phase-one specifications.

## Deploy and accept

Use a fresh isolated synthetic authority. Do not migrate, reseal or adopt an
existing authority automatically after the changed code basis. Independently
review this combined source and pins, then retain its first push and PR workflows
on Python3.10 through3.13. Capture actual full-stream summaries or first failure,
source maps, package reports and an independent RAW review. Method definitions,
static manual checks and earlier source successes do not close that gate.

Actual binary/installed new-component tests, custom pure/SQL capture, same-account
urgent capacity, four-side matching reconciliation, product calibration,
replicated recovery, sustained10000/s/30-minute/long stability and real-funds
approval remain OPEN. No kernel quota, hard native I/O bound or production
qualification follows from this milestone.

## Rollback

Return to the matching prior reviewed complete deployment and inventory on the
engineering authority. Never replace confirmed commands, fills, positions,
funding obligations or journals with an older snapshot. Reconcile unknown effects
before changing writers. The verification artifacts have no financial schema
migration; removing them does not erase their historical failures or qualify
earlier unaccepted code. Production, HA, D2 and real funds remain NO_GO.
