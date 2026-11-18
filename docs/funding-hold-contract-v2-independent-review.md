# Funding D1 v2：独立金融与验证规则审查

**有限规格结论：ACCEPT_FOR_CODE_ONLY；未发现阻塞纯 D1 v2 实施的政策矛盾。** 审查固定 `2bb8095faa76ca7d18f957590c7816ba44018554` 的两个新增文件，结合 PR61 rev2 `8008a0b24e8dc0095420b18f6b154c9db655a183`、其独立审查 `446af54a5da53728de006ead3afc8f752df2bd4c` 及 schema 提案 `895bcf51d9a39f126c1feecdcdb47daaa0a6f05b`。这只批准下一步 CODE 设计依据；不批准生产候选、参考实现正确性、目标执行、资金接入或上线。

没有运行或导入目标/参考，没有编译、SQL、worker、线程、proc/PID 查询、网络或 CI。`4e2b41d64b867e0b3a29e3c3ca25bc64f9d0e357` 只做原始字节哈希和 DTO/签名 AST 数据核对，没有使用生产算法、DTO 校验器、builder、哈希/舍入 helper 或其金融答案。旧参考 `e6c2c3e5075665d9f61cfc752ccc04d7a6b16e0f` 保持不变、未运行；不能将本规格结论倒签为它已符合 v2。

## 规则结论

完整 `expected_active_stage` 与 revision 并用，要求先验证同 duty/rule-scope 的整个 Stage，再比较 kind、amount、exposure/cap/final 引用。单 CAP ref 不再能掩盖另一 exposure；旧参数必须明确拒绝，不推断转换。这里只验证提供的表示，仍不能认证 cut 内容、唯一性或持久 CAS，也不允许改写最终值或 APPLIED。

895 的 policy/action 字节此前只是候选选择，2bb 现在明确把它们采纳为新的本地 D1 决策，未声称它们早已属于 PR61。Duty 九字段、policy 七字段、action 七字段按 exact typed canonical ASCII JSON 独立 SHA256；duty/action prefix 在 hash 之外，policy 是只允许在 typed WaitPolicy 上解释的裸 digest。该 digest 不给授权、批准或新预算；未来 domain-separated 版本必须另编号迁移。此范围内没有金融或身份歧义。

action 明确绑定 account、USD、稳定财务 generation 和真实 root encumbrance lineage，排除 scale/policy/duty/claim，避免分裂或改名重置预算。不同 approved scale 应冲突，而不是新增 action。first policy 来自批准且有效的不可变风险配置；历史未知、冲突或不可用时保持限制，不准初始化/dispatch。每个实际 child 查询共用一个 count，root 关闭须覆盖所有 child 和在途义务，迁移必须导入映射与全部历史。以上是明确的 D2 责任，D1 字符串或局部 tuple 不能证明它们。

等待 revision 现在统一按记录变化计数：先算 highwater、attempts、last-dispatch、sticky default；非 revision 字段全部不变才返回同 revision 且不计 query，变化则只增一次并先检查溢出。此规则对 normal/default 相同，消除了旧参考的任意观察增版选择。到 deadline 等号不发 query；interval 等号只有在 deadline 之前且仍有预算时才可计数；最后一次允许尝试计数后进入 default。未知 dispatch、restart 和新 duty 不退款、不延 deadline、不清债或解锁。

特别地，最大 revision 的“same-time no-op 成功”只适用于真正没有任何字段变化。若外部给定记录尚未 default，而本次在相同 highwater 下首次发现 deadline/预算已耗尽，则 sticky default 是一次变化，最大 revision 必须拒绝；不能把它误作 unchanged 成功。overflow 拒绝也不能放弃原债务或限制。

2bb 没有更改 PR61 的 `H=P+U`、N 不抵 H、base 排除 funding、accounting/risk/available/raw spend 一次计量，以及真实 F backing 的条件付款投影。WAIT 无变化、F=0 可投影负现金、其它 H 保留；eligible 仍不是 ACK、ledger receipt、APPLIED 或恢复许可。没有新增借币本金、利息、费用、估值或资本替代规则。

## 可实施的独立参考 delta

1. 用新版本 wire/新不可变输入版本，不改写 e6/75358 历史；先冻结新 API 和支持切片。JSON arrays 与 Python exact tuple 的转换须显式、可审，所有未知/缺失/重复键及 bool-as-int 仍拒绝。
2. 从公开 9/7/7 exact 字段自行构造三个 hash payload；增加 policy/action identity 检查，输出完整自然 slot 六字符串有序 array，不能继续用旧 object 再删字段比较。hash 结果在实际执行前仍是 CODE_DEFINED/NOT_RUN，不是已验证结果。
3. 新增 895 已获采纳的 duty 时间切片：不早于 1970 UTC，距纪元的整秒必须可被 interval 整除；使用精确整数日/秒而非 float timestamp。旧 e6 的 calendar-only 校验不够。有效 seed 的日期须按新公开规则对齐，另保 pre-epoch/未对齐拒绝样本，并使用新的 suite 版本保留旧含义。
4. `stage_advance` 改完整 expected Stage；独立验证 expected/proposed/current 的 exact types、同 key/scope 引用。新增 same CAP/different exposure、same refs/different amount、well-formed final P/N kind mismatch、跨 duty ref、stale revision、旧 keyword、不变输入的反例。不要借生产 active_ref helper 构造 oracle。
5. 等待 expected policy 使用本参考自己算出的规范裸 digest；记录先投影字段，再决定是否增 revision。覆盖 normal/default 同时刻无变化、highwater 变化、last attempt、deadline/interval 等号、MAX revision 真 no-op/变化两类、固定 start/deadline 溢出与时间回退。
6. action 根据权威提供的 root lineage 构造七字段身份；policy、scale、rule scope、duty、claim 不增加另一预算。局部集合重复/冲突必须拒绝，但不得宣称全局历史完整或 first-policy 已授权；empty collection 不是新预算许可。
7. 保留手填金融切片原值、512+512 的封闭合成输入意图、真实错误/不支持/技术失败区分及全部 false activation。新 seed 含义改变须记录为新 v2 输入，不能为了匹配生产运行结果修改期望。原 M10 仍只校 U600→P246 等给定量；M14 quote80 与 D2/whole-period 仍不支持。
8. target bridge 独立 CODE 审查；完整值、computed identities、错误分类及关联版本按已声明支持域比较。不得忽略字段、用生产 DTO/validators/builders/rounding/hash helper 写参考或把未知异常洗为业务拒绝。完整 DTO 的可达历史/输入域须显式；不能从未公开的生产 validator 推断新的金融规则。

这是实施清单，不是已写的新代码。下一 production/reference source freeze、独立 CODE 和首次有限运行计划仍各自必需。

## 验证证据与门槛

数据核对：895 的 13 个 DTO 字段清单和 15 个公共签名与固定 4e2b 的 AST 相同，目标源码 **23,278 字节**，SHA256 `5c41504f58ae97c4437e7887985ef71bf65ce11b34b5d1bf923b08b6c529e67f`。这只确认提案绑定的旧 schema，不证明其已实现新完整 Stage/no-op 规则。三个数值域上界与直接整数公式一致；2bb 相对 895 只有两个新文档/JSON，runtime 变化为零。无金融/哈希程序执行结果。

后续至少保留 16 个边界测试组及现有正确性检查，详见 [review.json](../evidence/reviews/funding-hold-contract-v2-independent/review.json)。D2 的真实 ACK/outbox/ledger、完整 root lineage/history、批准政策、唯一写入者/旧 writer fence、whole-period atomicity 和 restart/reconciliation 都继续 BLOCKED。生产、HA、容量和真实资金无 GO。

部署仅发布本两文件审查工件供 CODE 工作使用；无金融能力、数据库变更或迁移。回滚只撤销审查提交，不变更 8008/895/4e2/e6 原件或任何已确认经济历史。未来执行证据另封，不回写本次 NOT_RUN。
