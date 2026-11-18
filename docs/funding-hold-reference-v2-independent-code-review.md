# Independent Fraction reference v2：有限 CODE 审查

固定源 `61259db94051ff40b1882f6d17ab24c107e3527d`，parent 为冻结资源合同
`061580ce8c13120751bde4c4ce631b9dff25aa67`。结论：
**CODE_OPEN_BLOCKED / NOT_RUN**。发现 RV2-B1：final active 的 cap/exposure
lineage 被源码强制清空，但当前公开 typed shape 允许 refs，先行政策未明确
批准 history-only 表示。root 已选择新的 immutable-lineage-retained 澄清规则；
原 612 必须保留，另提合同与代码修订，不能签 full-stage CODE 闭合。
完整 decoder 等价、参考自检、目标差分、资源峰值及生产验收也均未闭合。
机器证据见 [review-61259db9.json](../evidence/reviews/funding-hold-reference-v2-independent/review-61259db9.json)。

## 来源与独立性边界

完整阅读 572 行 oracle、411 行 generator、486 行测试及各冻结 wire/resource
修订。11 个新自身工件共 126,394B（不含 manifest）物理/Git SHA/length 一致；
wire 原件 31,492B，SHA
`d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be`，
与 061 冻结对象相同。旧 e6 的十个工件逐项 Git 字节相同，原 manual 亦不改。
`uta/` 相对 e6 的 Git 差异为零。

静态 AST 核对五个自身旧金融函数 `_money/_major/_units/_aggregate/_base` 和
三个 `_evaluate` 金融分支 aggregate/decompose/payment_precondition 的 AST
与原 e6 相同。它只说明这些自身源码子范围保留，**不证明调用链总语义未变**：
v2 的 stage/history/epoch/CAS/transport 验证确实按新合同另行改变。

oracle 依赖仅 datetime/Fraction/hashlib/json/math/re；generator 仅 hashlib/json，
不导入 oracle、生产核心或 DTO/adapter。测试只导入这两项自身 helper 与 stdlib。
审查员此前在另一任务读过旧 4e2 纯模型，本次不是 oracle 作者，未读新的生产
core、adapter、fc1/ed81 算法，也未从目标/参考执行结果取得答案。作者未读取生产
实现的事实作为任务给定 provenance；静态依赖检查不是文件访问历史的取证证明。

本轮仅 Git/文件字节/JSON/静态 AST 和公开合成字面量的标准库 SHA 检查，
没有 import、字节编译、调用或生成 oracle/generator/test/target，也没有 SQL、
时钟、proc/PID、actor、网络或 CI。三个 identity 字面量哈希核对属于独立
数据检查，不是 reference/target hash 测试 PASS。

## 数值与阶段

USD scale 2..8、单腿 abs<10^38、总 P/U/N<=1000*(10^38-1)、derived
abs<=4000*10^38 保持 exact native int 边界。transport 可接收 finite float，
但金融/time/schema 字段 exact-int 检查拒绝其及 bool；不经 binary64 转钱。
参考先将 minor units 变成 Fraction major units，返回前要求乘回 scale 后
denominator==1。P/U/N 分开聚合、H=P+U、N 不抵风险或普通现金占用。

base 明确 EXCLUDED；应计 base-P+N、风险 baseRisk-H、available 再减原 IM/
挂单 reserve，F 已在给定 baseRisk 内；ordinary cash=C-F-H。未重算 IM/MM、
资产、借贷、资金费率或资本。backing 是先行确认 fact 和 F<=max(C-ownP,0)
的条件投影：WAIT 不变，eligible 只去自身 P/H，其他 H/N 保留，F0 可负现金。
缺 quote 只输出 recheck，绝不成为已付款/健康或实际授权。

DutyState 验证完整 registered 起始/history/revision 和每个 stage/ref；只能
registered→U/final、U→P/N/zero，final 不再改，cap 不越界，不支持 APPLIED。
最终 active 的 exposure/cap 被强制要求为 null，旧 U 引用只留在 history，
是本次阻断项，不能据 nullable typed schema 推断该语义已获批准。
expected stage 对同 duty/scope 先验证后完整相等比较 kind/amount/三 refs，同时
检查 revision 的代码路径存在；它不能补偿 proposed/new history 的上述表示缺口。
legacy 单引用在 valid envelope 内按明确优先级 UNSUPPORTED。均不认证实际内容。

## RV2-B1：final lineage 语义未闭合

源码 `reference_funding_hold_d1_v2.py:223–225` 拒绝所有带 exposure/cap 的
FINAL_PAYABLE/FINAL_RECEIVABLE/FINAL_ZERO。generator `stage:45–52` 对三类
final 一律只给 final_ref，U→final 的正例和测试 M10 也沿用它。
`_allowed_step:231–237` / `_state:240–255` 只检查阶段顺序与 amount<=cap，
没有按历史 U 验证最终 lineage 的保持。

未执行的有界反例：同 duty/scope 的 registered→U600，U 持有 refs E/C。
proposed P246 完整保留 E/C 并另有 final F，expected current Stage 与 revision
都正确时，当前参考会在 `_stage` 拒绝；相同 proposed 把 E/C 都设 null，参考
则接受并返回 active 中的空引用。receiver246/zero0 相同。P/U/N/H 的数字可以
完全相同，因此只比 status/count 或金融数值不够，必须检查完整 Stage 内容。

061 的 typed Stage 两字段都是 null-or-ContentRef；2bb 只明确更换 CAS 等政策，
没有先行写出 final history-only/retained 的选择。此次首先定位的是公共语义
缺口，不以读取新生产函数补参考答案。root 现选择本系统新增澄清：

- 直接 registered→final：exposure/cap 都必须 null；
- 经 U→final：final 必须逐字段保留历史 U 的 exposure_ref 与 cap_ref，三种
  final 均相同；丢失或更换拒绝，final_ref 另必填；
- 旧 U 仅历史不再贡献，只有新 P/N/zero active；保留引用不重复计量，不等于
  内容认证或持久历史证明。

这项选择来自审计可追溯和 cap 来源需求，现已另行冻结为公共规则
`69a3e32e9d267295f223671e62f17b2f9e71eb70`，等待独立短范围规则审查。
不能静默改原 061 schema/612/e6、generator 输入或旧 NOT_RUN 元数据。
它是前向澄清，不把原先歧义追认成已明确定义的旧规范，也不制造 612 的实际
运行失败结果；本报告的反例仍只是固定源码的未执行控制流分析。
参考作者须从该公开新规则另交 oracle/generator/tests delta；bridge 不得替旧
null proposed 自动补 refs 来“匹配”目标。原 612 在此之前保持 BLOCKED。

## Identity、等待与全字段输出

公开 8008/2bb 规则分别给出 9/7/7 canonical payload；独立构造 sorted/ASCII/
无空格 JSON，duty/action prefix 在 SHA 之外，policy bare digest。六字段 slot
返回有序数组，聚合同时检查 duty hash 与 slot 去重。period 使用 integer
days/seconds 校验 >=epoch 和 interval 整除，不读钟、不用 timestamp float。
这些新 policy/action 选择是 2bb 的明确纯比较合同，不回填为旧 PR61 既有规则
或旧 4e 的批准状态；哈希亦非政策审批和预算权限。

wait 先投影 highwater/attempt/last/default，真正不变保 revision；变化只增一，
MAX revision 变化拒绝。normal/default 同一规则，到 deadline 等号不查询，
interval 等号只在未到 deadline、未用尽预算时计数；最后一 attempt 计数后
review sticky。未知结果没有退款路径，首次 start/deadline 不延长。last-dispatch
形状须在 start..min(highwater,deadline-1)，query budget/time 都为有限整数。

十个 op 都有显式完整 value：Identity、DutyState、Totals、Decomposition、
PaymentProjection、WaitProjection 与全部 sorted action_ids，而非 count-only。
所有 activation_permission=false、holds_unchanged=true 的固定输出遵守 wire；
提供对象的 output-only flag 亦检查，未用 marshalling 静默洗掉输入字段。
未来目标 bridge 必须从真实目标 API 返回值完整序列化，不能据本参考公式
代造字段。bridge 不在本源，也未因此通过。

## Transport 与错误分类

迭代 walker 将 root 计 depth0；每个容器/标量出现计一次，dict key 与 value
分别在 parent+1 计数。waiting 只计未访问数据节点、exit frame 不计节点，
对子项先作 visited+waiting+child_count 下界检查。path-local active ID 集合
只拒 ancestor cycle，普通 alias 退出后重新按路径计数，不作全局去重。
depth32/nodes250000/128 decimal digits 均 inclusive；整数负号不算位数。

raw loader 明确 UTF8，不推断 UTF16；拒 BOM、非法编码、重复 decoded key、
NaN/Infinity，1e999 解析得到的 Inf 也由 walker 拒绝。finite float 可过 transport
后在 typed DTO 拒绝；不是把 typed negative 全误归 wire error。原 raw UTF8 与
解码后 compact ASCII 分别限制 2 MiB。native evaluate 没有原 raw 字节可查，
负责 native tree/compact 上界；raw 字节上界属于 loader。

预算/transport 校验发生在 business catch 外；envelope 的 exact keys/schema/
case_id/op/input shape 也先完成。坏传输或 envelope 抛 WireReject，无伪造 case ID。
已知业务输入/前置拒绝和不支持才归其两个显式 reference 异常族；bare
RuntimeError/ValueError/TypeError 等不由 evaluate 的 business handler 泛抓。
当前实际数据路径上，WireReject 由前置 walker/envelope/loader 产生并逃出。
未知技术失败不能作为“双方都拒绝”的通过结果。

## 仍未验收的范围

30 个测试方法与 D1V2 1024 个 seed **只是定义**。静态分区为八类各 64 valid
+64 negative，identity valid 内32 duty/16 policy/16 action，十个 op 均有声明
输入。没有生成它们，没有逐 seed 的实际分类/返回值或最大编码结果。
原 manual 仍是17 decompose+11 payment+2 special 和27行 slice/unsupported，
不是27整例通过。若未来选全部30方法，内部多个1024循环意味着请求数远大于30，
必须由新的实际资源/执行计划计量。

测试定义包含完整输出 schema/action_ids、边界、alias/cycle 和未知 RuntimeError；
其内置 schema checker 只是所用关键词的局部实现，不是通用 JSON Schema 认证。
bare ValueError/TypeError 的额外 fault injection、dict-key 节点等号及 alias 展开
预算反例仍可在后续验收补足，不将这些未执行覆盖项说成已通过。

JSON parser 和 compact encoder 先分配再验证部分大小；2 MiB/节点规则不是
内核 RSS、分配峰值或 CPU 硬限额。完整 decoder equivalence、性能与资源峰值
保持 PENDING / NOT_RUN。没有从所选静态路径推导全部 Unicode/组合负例或
target/reference codec 已等价。

提供集合/refs/first policy/root allocation lineage/跨代历史和 shared-action
权威存储均未认证。全局唯一、真实 dispatch/ACK/outbox、先行履约、旧入口 fence、
付款/完整 period 原子性/重启/真实资金与生产 D2 仍无条件 BLOCKED。

本交付仅两份 SAFE 审查资料；未改作者源、e6、061、规则、旧 raw/计划或 runtime，
未 push。回滚只 revert 审查提交。先以新 immutable policy/source 关闭 RV2-B1，
再另审 bridge、有限 caller 与 exact 首次资源 scope，才可能授执行 GO。
本结论不授任何实际运行或金融能力。
