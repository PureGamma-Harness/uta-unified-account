# 独立 funding D1 v2：完整 wire 与 CODE_ONLY 参考

新增三个独立测试侧文件，旧 `e6c2c3e5075665d9f61cfc752ccc04d7a6b16e0f` 的三个源文件、22 个测试定义、1024 个种子定义、原 proposal/manual/manifest 均保持原字节和 NOT_RUN。本分支从 e6 开始，分别冻结 `2a204f064ddda782547993fa4a16e669bbbcd907` 的逐 op 合同、`2e6ad129804eebbf0d8682f3f0b0855ebfd8ea5c` 的完整 action_ids 修订、`a33da70026a5b0d36d5df57ae8a5736a64914ab1` 的传输关联边界、`061580ce8c13120751bde4c4ce631b9dff25aa67` 的新增资源合同；本 CODE 依此最后版本实施。

唯一规则依据为公开 8008、895 和 root 的 `2bb8095faa76ca7d18f957590c7816ba44018554` 新政策，并经 `86b3c2ac0b41b526cf8ebba2b3babda0b4b97ad1` 有限独立规则审查。没有读取新的生产实现、helper、builder 或运行答案，没有导入生产模块或复用生产 DTO/验证器/舍入/哈希函数。自身参考的 Fraction 数值路径直接来自规则；生成器不导入参考，合成输入与期望分类不由目标输出决定。

## 完整公开接口

[wire-contract.json](../evidence/designs/funding-hold-exact-reference-v2/wire-contract.json) 列出十个 op 的 input exact keys、全部 value 输出字段/类型、13 个 DTO 及 identity/元数据对象、常量标志、数值范围和错误分类。它定义的是独立比较协议，不是已部署的 UTA REST/JSON 服务。

| op | 目标侧允许的调用/序列化 |
|---|---|
| duty_identity | 给定 DutyKey 的完整 payload、duty_id、六字符串有序 natural_slot |
| policy_identity | 给定七字段 policy 的 payload 与 `.digest` |
| action_identity | 给定 ActionKey 的七字段 payload 与 `.action_id` |
| stage_advance | 完整 expected_active_stage + revision，返回整个 DutyState |
| aggregate | 完整状态集合、scope、basis_complete，返回整个 Totals |
| decompose | 目标 aggregate 后调用目标 decompose，返回整个 Decomposition |
| payment_precondition | 所有给定 backing/prior/quote 字段调用目标，返回整个 PaymentProjection |
| wait_preview | 完整 record、外部 now/revision/policy digest/dispatch，返回整个 WaitProjection |
| wait_records | 序列化真实 validator 返回的全部 action IDs，原顺序不修正；另给 input count 和固定标志 |
| unsupported | 必须明确返回已知 unsupported 分类，不能产生成功金融结果 |

不能只比较 count、status 或字段子集称 full PASS。bridge 应只做 exact DTO 构造、调用和全字段序列化，不自行推导风险/现金/等待公式；derived 数字必须来自目标 API。tuple/array 映射及 init=False flags 的验证/省略属于显式 marshalling；不得静默忽略输入字段或修正目标返回顺序。bridge 仍由另组独立 CODE 审查，本提交没有该实现。

顶层 schema=2，hash_wire 固定 `CODE_CONTRACT_IMPLEMENTED_NOT_RUN`。只有有效 envelope 才能产生同一 case_id 的响应：已知输入/前置拒绝为 `REJECT / REJECTED_INPUT_OR_PRECONDITION`，已知不支持为 `UNSUPPORTED / UNSUPPORTED_OPERATION_OR_CAPABILITY`。reference 内部细诊断不是目标 ABI。未知构造器/内部异常逃出为技术失败，不能泛抓 ValueError/TypeError/Exception 给其业务标签。

无有效 case_id、错误顶层 keys/schema/op、非对象 input 或损坏传输必须抛出 ReferenceWireReject，不能伪造 INVALID case_id 或业务 response。JSON 读入只接受 UTF8，拒绝 BOM、重复键、非有限数、非法编码和超过 2 MiB；不做 UTF16 推断。受支持域 JSON Schema 约束之外的负例仍应按明确的“拒绝/不支持/传输错误”合同处理，不能把所有 schema 错误笼统归类。

061 的资源规则是另一次明确公开的 transport 决策，不是从 adapter 实现学习金融答案。独立迭代 walker 令 root depth=0；container/scalar 每路径出现计一次，dict 的每个 key 与 value 也分别在 parent+1 计数。depth≤32、nodes≤250000、整数十进制位数≤128（不含负号）；普通 alias 重复计、祖先路径 cycle 拒绝。raw UTF8 与 decoded compact ASCII 编码分别≤2 MiB。finite float 可通过 transport，然后由 exact typed field 拒绝；NaN/Inf、包括 1e999 解析溢出，是 transport 错误。实现未读取 adapter core。

同一 valid envelope 中，legacy `expected_active_ref` 出现即优先 UNSUPPORTED，即便其它 stage input 字段缺失；但坏 envelope 的 transport 错误仍先处理。codec 同合同不等于实现已证明等价，**decoder equivalence 继续 PENDING**。这些是验证上限，不是标准 JSON parser native allocation/RSS 的内核硬限额。

## 新规则实施

Duty 日期不早于 1970 UTC，距纪元整秒必须可被给定 interval 整除；使用整数 days/seconds，不用 float timestamp 或读钟。canonical payload 独立构造为 9/7/7 个 exact 字段：duty/action 的 prefix 在 SHA256 之外，policy 为 typed content 的裸 digest。scale、duty、claim、policy 不给同一根 action 另一个预算；提供集合内的重复 action 冲突。所有内容/批准/完整性事实仍是外部输入，哈希不是授权。

CAS 对同 duty/scope 的完整 Stage 先独立验证，然后比较 kind、amount 和 exposure/cap/final refs 及 revision。单 ref legacy 参数明确不支持。可达纯 history 仍只覆盖 initial→U/最终值、U→P/N/zero 两步，不认证持久历史、不修改最终值或 APPLIED。

等待先投影 highwater/attempts/last/default，完全无变化时保持 revision 且不计 query；否则只增一次并在返回前拒绝 MAX revision 溢出。normal/default 共用这一规则。deadline 等号不查询，interval 等号仅在 deadline 之前且仍有预算时计数，最后一次尝试计数后 default；未知结果不退款。最大 revision 下，若本次需要设置 default，就算时间没变也不是 no-op，仍拒绝。所有输入保持不变。

原 Fraction 公式未改变：H=P+U、N 不抵 H；base 明确不含 P/N/H，accounting=`base-P+N`、risk=`base-H`、available=`risk-IM-orderReserve`，F 已在 baseRisk 中只计一次；ordinary spend raw=`C-F-H`。支付只作 own P/backing 投影，WAIT 无现金或 hold 变化，F=0 可投影负现金，其它 H 保留。没有新借币、资本、估值、IM/MM 或金融接入。

## 有限测试定义与证据

30 个测试方法仅为定义，全部 NOT_RUN。D1V2-SEED-0000..1023 是新输入版本，仍为八类各 64 valid+64 negative，共 512+512。有效 identity 类分为 32 duty、16 policy、16 action，保证十个 op 都有输入；完整 Stage 负例、对齐/纪元和 MAX revision 边界按新规则显式加入，不回写旧 seed 的含义。

新增方法包含 policy/action 字面 payload digest、action scale 排除、period 纪元/对齐、双引用/amount/kind CAS、normal no-op、MAX revision、deadline/interval 等号、完整输出 schema/action_ids 与 transport 错误。原 manual 文件逐字保留：仍只有 17 decomposition + 11 payment + 2 special 的切片，27 行矩阵无一被改写为完整场景通过。M10 只给定 U600→P246 等；M14 quote80 和真实 D2/whole-period 不支持。

同一 transport 方法还定义了 depth32/33、128/129 digit、250000/250001 node、400000 个非 ASCII 字符造成 compact-size 越界、finite/nonfinite 与 alias/cycle 反例；这些 fixtures 也全部 NOT_RUN。30 方法包含多次固定 seed 自检循环，不代表仅有 30 次请求或一个已执行的 1024-case differential。

本次实际检查仅 Git/原始字节/AST/JSON 与两组公开 policy/action 字面数据的标准 SHA256；**没有运行参考、生成器、测试、目标、SQL、actor、线程、proc/PID、网络或 CI**。字面数据 hash 是测试向量的数据来源，不能记为参考/目标 hash 测试 PASS。单请求 2 MiB、1000 duty 与输出范围有 CODE/断言定义，实际最大编码大小、耗时和资源峰值均 NOT_RUN。

后续须另一组对不可变 CODE 和 bridge 分别审查，root 再给 exact 首次有限 differential 或 normal CI 计划。参考自检、目标差分、CI、D2 持久化、性能及 HA 必须各自报告，不能互相代替。

## 部署与回滚

只有新的测试侧源、合同、配置/证据模板；UTA runtime 零变化，所有 activation_permission=false。未实现真实 dispatch/ACK/outbox、批准 first policy、root lineage/history、全局唯一、账务提交/APPLIED、旧 writer fence、整期原子性、重启对账。D2 和真实资金/生产启用继续 BLOCKED。

评审发布这批 CODE_ONLY 工件不会部署金融能力或迁移数据。回滚移除新 v2 文件/提交，保留 e6、各 wire 冻结点与原金融历史；未来首个运行结果另封不可变证据，不编辑本次 NOT_RUN 元数据。
