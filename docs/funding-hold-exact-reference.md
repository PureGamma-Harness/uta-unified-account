# 独立 funding D1 精确参考：CODE_ONLY

本次提交增加测试侧 Fraction 参考、封闭合成输入生成器和测试定义；没有运行它们，没有接入 UTA。`activation_permission=false`，D2、真实资金、性能和故障恢复均无批准。基线为 `ef7508bebd35cac71d9db8fdda896806ce4ade64`。独立计算直接推导自 PR61 rev2 `8008a0b24e8dc0095420b18f6b154c9db655a183` 及独立规则审查 `446af54a5da53728de006ead3afc8f752df2bd4c`。

生产候选 `4e2b41d64b867e0b3a29e3c3ca25bc64f9d0e357` 仅用于定位 schema 名称及接口签名，不导入其模块、不复制 DTO、校验器、builder、哈希或舍入函数，不从生产运行结果制造参考期望。实现是不同的 Fraction 主币数值路径；每次恢复最小单位须整除，不能用 float、默默截断或饱和。

## 已定义的有限切片

USD scale 为原生 int 2..8，全体一致；金额为原生 int，输入绝对值严格小于 `10^38`；最多 1,000 个 duty。P/U/N 总贡献不超过 `1000*(10^38-1)`，输出派生量绝对值不超过 `4000*10^38`。C 与 base 权益可负；P/U/N/F/IM/MM/orderReserve 非负。可支出显示值可 clamp 至零；其 raw 值、负权益及负现金保留。

Duty 使用 8008 的九个 exact canonical 字段和独立 SHA256；自然 slot 使用六个经济字段，改变 interval/rule scope 不能制造同 slot 第二项。内容引用只校类型、形状和同 duty/rule-scope 链接，不认证被引用对象、批准目录或来源。

纯状态仅覆盖 REGISTERED → U/最终值、U → P/N/zero 的可达历史。最终值必须在给定 U 内；历史保留，P/U/N 只有一个活跃贡献。REGISTERED 不能被汇总为零。所谓 CAS 仅比较传入表示，不是数据库事务、账户版本或写入者 fencing。当前 proposed `expected_active_ref` 为 CAP 或 FINAL_CUT 单引用；完整 exposure+cap 的认证/CAS 未由此证明，见下方未冻结协议。

`H=P+U`，N 不减少 H。base 必须明确 `funding_components=EXCLUDED`，accounting=`baseAccounting-P+N`，risk=`baseRisk-H`，availableRaw=`risk-IM-orderReserve`。baseRisk 已反映真实 spot F；不再扣 F。ordinarySpendRaw=`C-F-H`。IM/MM 和 base 都是外部输入，参考不计算估值、借贷本金、利息、新 IM/MM 或借币额度。

付款仅为条件投影：外部给定先前已确认义务已清，而且 `F<=max(C-ownP,0)`，才投影 C 减自身 P、P/H 释放自身量，其他 U/P 和全部 N 保留。自己的 H 不是强制履约拒绝条件。F=0 可投影负现金；非零 F 不能跨越真实 backing。WAIT 保留原 C/P/U/N/H。无 quote 只产生 risk-recheck 要求，不产生风险恢复许可。此投影不是资金过账、债务解除、ACK 或 APPLIED。

等待只处理外部提供的 now/highwater、首次 start/deadline、完整 versioned policy 和共享预算。deadline 相等即超时，预算耗尽即 DEFAULT_REVIEW。查询先计入预算，未知 dispatch 不退款；同 action 的多份记录、改 policy 或 scale 的预算重置均不能在同一提供集合中去重放行。DEFAULT 不释放 H、清债、自动解锁或重置 deadline。纯函数不能认证首次记录，也不能防止调用者在下一次请求伪造完整的新历史；这些属于被阻塞的 D2。

## 尚未冻结的 wire 与语义

接口提案见 [wire-scope.json](../evidence/designs/funding-hold-exact-reference/wire-scope.json)。所有响应包含 `hash_wire=NOT_VERIFIED`。唯一有 8008 canonical bytes 的经济 duty hash 已独立编码，尚未执行；policy hash、action hash 的公开字节协议尚未固定，不能猜 namespace、删字段后称 full exact 或把逻辑 tuple 当原始 hash 相等。

自然 slot 在独立 wire 表示成六字段对象，不冒充生产内部容器。action 逻辑标识显式使用 authority/generation/account/USD/allocation/action-kind/terminal-goal，排除 duty、executor claim、policy 和 USD scale；它是当前 scoped-allocation 提案，完整 action hash 及账户 namespace 仍待单独规范审查。没有 target bridge，不存在全字段差分通过。

8008 未定义纯观察/no-op 是否提高 revision。本参考暂将非 default 的观察投影记一次 revision；相同 highwater 的已 default 记录返回原记录，后续 highwater 提升 revision；预算不能因这些观察重置。这是显式本地提案，不能当已获批准的交易所规则或已证明生产一致。可达 duty 状态中的 revision 等于历史转换数、历史最大两步，亦仅是本参考切片规则，不接受任何数据库迁移或纠错序列为此倒推。

以下闭合需公开补充规则和另一次 CODE 审查：policy/action canonical bytes 与 schema 版本；scope 中账户、scale 的 hash/逻辑 namespace；active-ref 的完整预期 stage/exposure/cap CAS；无操作和 default 的 revision 事件粒度。后续 bridge 必须将缺字段或未知异常列为 NOT_VERIFIED/技术失败，不能选择性比较后输出完整 PASS。

## 合成例与测试门槛

[manual-slices.json](../evidence/designs/funding-hold-exact-reference/manual-slices.json) 有完整 27 行支持矩阵，全部标为 SLICE_ONLY 或 UNSUPPORTED；只有 17 个 decomposition、11 个 payment、2 个 special 手填数值切片。M10 只使用已经给定的 U600 → P246/N246/zero，不计算 rate/cap。M14 borrowable quote80 不支持。M15 存储恢复、M17 资本/舍入和 M27 全期跨账户结算不支持。人工 expected 字段只证明对应切片，不能称原 27 例通过。

生成器只定义 seed 0..1023，512 个有效、512 个拒绝/不支持输入，八类各 64+64。域外 seed、bool seed 拒绝；无需随机熵或系统时钟。边界包含 0、等号、负现金、scale 2..8、金额 `10^38-1` 与越界、1000/1001 duty、时钟/版本/保留金额和共享 action。只流式逐例生成，不存全体 JSON，预设单请求最多 2 MiB。该上限目前只有 CODE/测试断言，未运行测得最大值。

22 个 unittest 方法全部 NOT_RUN。未来分开报告参考自检、人工切片、完整 wire 合同、生产差分和 D2 持久化，不得混用结果。未知内部异常原样抛出；仅明确的 ReferenceReject/ReferenceUnsupported 可分类，业务拒绝不能给技术失败洗绿。

首次有限执行必须由 root 审查当前不可变代码及独立执行计划后决定。本提交不授权执行。届时可提议只运行本文件的 unittest discovery，固定执行输入/资源/原始输出，禁止安装/SQL/UTA import/worker/网络；参考通过仍不是 target 通过，更不是接入或上线门槛。详见 [execution-gates.json](../evidence/designs/funding-hold-exact-reference/execution-gates.json)。

## 部署与回滚

无 runtime 文件变化、服务连接、资金 schema、数据迁移或默认 capability。评审时核本提交只含指定 tests/docs/evidence，所有执行门槛仍 NOT_RUN。发布此 CODE_ONLY 工件仅供审查；不能将它作为账户风控或资金授权服务。

回滚通过撤销本工件提交或移除新增的三个测试侧 Python 文件与本说明/元数据；无持久金融状态需要回退。最初 proposal 提交单独保留，原 8008/446af/27 例/生产候选/历史失败证据不改写。若未来获准执行，原始结果须另提交；不得回写本次 NOT_RUN 状态。
