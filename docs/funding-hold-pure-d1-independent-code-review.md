# Funding Hold D1：独立有限 CODE 审查

固定候选 `4e2b41d64b867e0b3a29e3c3ca25bc64f9d0e357`，公开基线
`ef7508bebd35cac71d9db8fdda896806ce4ade64`。结论为
**CODE_CLOSED_FOR_DECLARED_PURE_SUBSET_ONLY / NOT_RUN / NOT_QUALIFIED**。
在已声明的原生整数、提供数据和条件投影范围内，本轮未确认新增的算术或
状态代码阻断项。这不是测试通过、完整参考差分、全规则 CAS 或金融接入批准。
机器记录见 [review-4e2b41d6.json](../evidence/reviews/funding-hold-pure-d1-independent/review-4e2b41d6.json)。

## 固定范围及静态证据

已完整阅读新增 594 行模块、351 行测试，以及先行协议、候选声明、27 行
支持矩阵。候选七项文件的物理/Git bytes、SHA 一致；模块为 23,278B，
SHA `5c41504f58ae97c4437e7887985ef71bf65ce11b34b5d1bf923b08b6c529e67f`。
原 65 个 Python 模块及 HTML 的 66 项 Git 对象逐项与公开基线相同，
合计 1,456,126B；新 review sparse checkout 未物化这些原文件，故不声称
此处对它们完成了全部物理副本检查。唯一 runtime 增量是未连接的新模块。

AST 仅做静态语法与声明检查：模块 39 个函数/方法定义，测试 22 个测试方法，
排序后的方法集合精确等于候选 inventory。模块不 import 任何 UTA 模块；
其显式依赖仅为 `__future__`、dataclasses、datetime、hashlib、json、re，
没有顶层业务函数调用。dataclass 定义未来 import 时的执行不等于本轮已 import。

没有导入/字节编译/运行目标或参考；没有测试、SQL、读钟、进程/PID/proc、
worker、CI 或网络动作。标准库 JSON/SHA 的独立字面量复算核对了 M18 唯一
固定 duty ID：`funding-duty:v1:3608a7a0ec99683dd080f6663ad9283a965df92c46878e569c3a8c467d3f7779`。
这只核对该 canonical duty 向量，未执行生产 helper，也没有验证 policy/action
hash 的规范性或参考实现的全覆盖。

## 数值与状态约束

`Scope`、`DutyKey`、Stage、DutyState、Totals、BaseValues、WaitPolicy、ActionKey、
WaitRecord 的输入路径先 exact-type，再访问后续字段/集合/哈希；金额、scale、
revision、时间和次数拒绝 bool、float、Decimal 与 int 子类。固定标识符 ASCII
有界；period 严格 UTC whole-second、真实日期且相对 epoch 按 interval 对齐。
原生 tuple 集合有 1000 项上限，没有对未知用户对象调用自定义 hash/getter。

令 L=10^38，n<=1000。每个 duty 只有一个提供的 active amount，0<=amount<L，
所以 P+U+N<=n*(L-1)，H=P+U；Totals 自身再次检查该约束。所有给定单腿绝对值
小于 L。应计/风险表达式绝对值小于 1001L，available 小于 1003L，普通 cash
raw 小于 1002L，单笔付款后 cash 小于 2L，均在显式 4000L derived 界内。
算术为 Python exact int，不经过 float、隐式舍入或饱和；唯一 clamp 为显示的
普通可支出 max(raw,0)。这不是 i64 或新估值内核认证。

DutyKey 的自然 slot 排除 schema/interval/rule scope；更换 interval/rule scope
虽可改变 duty hash，aggregate 仍拒绝相同自然 slot。DutyState 允许的链只有
registered、registered→cap/final、registered→cap→final；历史长度等于 revision，
cap lineage 不能改，超 cap final 拒绝，final 不可再转换，APPLIED 不支持。
每次聚合重新检查同 authority/generation/account/settlement/scale。提供集合不完整、
unassessed、重复 duty/slot、foreign ref 均不会按零处理。

decompose 的 base 必须显式 EXCLUDED。accrual=baseAccounting-P+N，
risk=baseRisk-(P+U)，available=risk-原 IM-原挂单 reserve；N 不抵 H，
spot F 不再从已含 F 的 baseRisk 重扣。cash-F-H 是额外普通支出约束，
不能当借贷、提币、订单或新 IM/MM 许可。

backing_precondition 先验证原 F<=max(cash,0) 和外部提供的先行确认义务 fact，
再检查 F<=max(cash-ownP,0)。F0 允许负 cash 的合成投影；F>0 不穿透真实冻结。
WAIT 保留 cash/P/U/N/H；eligible 只投影自身 P/H 的移除，其他 H/N 保留。
缺 quote 仅标需要重估，不认证支付或健康。它不消费原 DutyState、不写 cash、
不产生实际 ACK/APPLIED 或资本。

等待参数没有默认值，start+max_wait 检查 2^63-1 上界。preview_wait 检查提供的
revision/policy digest 与不回退 highwater；deadline 等号或预算用尽即 review，
不会再计新 query。允许的 query 先在返回记录中增加 attempt；接口没有退款路径。
review sticky、首次 start/deadline 不改、变化中的 revision 不饱和。真实 dispatch、
持久提交和输入历史的认证并没有通过这段纯代码得到证明。

## 明确保留的政策缺口

以下是 OP_GAP，不把已排除的生产能力伪装成新代码漏洞，也不据此签完整 CAS：

1. `WaitPolicy.digest` 的裸 SHA payload、ActionKey 无 schema/scale 的 payload 是
   候选选择。`895bcf51` 只是 wire 提案；尚非 PR61 既有规范或批准政策。
   该 canonical duty 单向量核对不覆盖两类 hash。
2. stage CAS 只检查提供的 revision 和 active_ref（pending 时是 CAP ref），并校验
   history/lineage；它不是独立 expected exposure+cap 双引用或完整状态 CAS。
   refs 仅 shape/link，不证明内容、规则授权或真实 duty 完整性。
3. 非 review 的同 highwater/no-dispatch 观察仍增加 revision；review 同 highwater
   返回原记录，较晚观察推进 revision。这是可见候选行为，no-op revision 政策
   尚待明确批准，不能自动算完整乐观并发语义。
4. validate_wait_records 只拒绝**提供 tuple 内**的重复 action ID。首 policy 选择、
   allocation lineage、全局唯一、丢失历史、新 generation 的迁移和每 duty deadline
   仍需权威存储与政策。输入可构造 DTO 不是 capability，缺历史不能凭它开新预算。

所有公开计算输出默认 activation_permission=false；DTO、digest 和外部 fact 都
不授金融权限。未调用或复用另一组参考核心；其 `hash_wire NOT_VERIFIED` 不被本报告
改写或提升为差分结果。

## 验收边界与回滚

27 个支持矩阵行全部标 full_case_supported=false / NOT_RUN；22 个方法只是定义。
现有测试定义覆盖主要正负切片，但没有执行证据；全域性质/并发/故障/参考差分仍未验收。
新增模块使候选 66py/67runtime；原 65py/66runtime 含义保留，normal CI 尚未准备，
本报告没有更新 CI allowlist 或默认政策。

真实 ACK、outbox、all-entry fence、完整 period 原子性、付款、重启、容量、真实资金
与服务接入 D2 **无条件 BLOCKED**。后续须先审新的有限 pure producer/源绑定和
独立执行资源，再由 root 分别授权；本 CODE 结论不是执行 GO。

两次行政 reader 偏差已保留：先误以为 sparse review checkout 物化原 66 文件，
FileNotFound 后改用 exact Git 对象；随后误以为 manifest 的方法列表按源码顺序，
实际为排序 inventory，改用同样的 sorted+count 比较。两者都是审查脚本假设错误，
没有目标/测试重跑或作者源修改。

本交付只新增两份 SAFE 审查资料。回滚 revert 审查提交即可；不改候选、8008/446、
895 提案、参考实现、旧 raw/plan 或金融数据。
