# Cross 引擎绑定：独立验证设计审查

审查固定提交 `53acece53d27fb118c89286c10e5be41bb2ca5e7`。结论为 **D0 设计方向可接受，实施与执行门槛仍未通过**。本审查没有发现需否决 D1 纯代码准备的新增已确认设计阻塞；它不是引擎实现、金融签字、执行 GO 或生产接入批准。

三份设计文件共56266 bytes与物理文件/Git对象逐字节一致。21项引用的 Git commit/path/blob/length/SHA-256 共673673 bytes全部核同；这些是跨快照静态引用，不是21份本机加载运行时证明。PR49→PR52/PR55 的运行时差异清单也与 Git一致。没有导入、编译或执行目标，没有SQL、进程/PID查询、worker、CI或外部服务调用。

设计已正确区分：固定实际调用对象与仅比较名称；函数code/defaults/closure和真正的globals/builtins lookup；类布局与仅编码类名；默认参考、同步shadow和保留但不允许的候选权威契约；十/十一字段策略和独立Credit V2；v1历史回放与v2原时点评估。旧writer排斥、只读打开和必须结算均被列为未来门槛，而非已有成功证据。受信进程/不可变镜像假设明确，未把同进程hash当沙箱、签名或写入权限。

以下是对原EBD门槛的独立可证性细化，全部未运行。它们承接设计中已声明的未实现工作，不应被改写为当前缺陷已经复现。

| 编号 | 实施前必须固定的证明 |
| --- | --- |
| EVG-001 / D1 | 实际 callable、globals 与 builtins：在可信初始化时建立固定对象 anchor；验证实际将调用的函数、函数自身 __globals__ 及 __builtins__ 解析关系，不只比较当前模块字典或名字。跨 helper 的可执行引用同样受检。 |
| EVG-002 / D1 | class layout 与稳定图编码：D1 固定 canonical 字节规范、逻辑节点/共享边/循环表示及 depth/node/item/byte 上限。进程内 is 身份校验与跨重启稳定 content digest 分开；不得把 id()/内存地址写成持久 binding ID。类方法、属性、dataclass defaults/default_factory 的执行边纳入有限清单。 |
| EVG-003 / D1_D2 | 默认与版本回放：默认十字段 valuation、十一字段 order、两个 cache 字段及 Credit V2 精确比较保留。新 envelope 必须显式版本分派。历史 v1 始终参考；v2 使用归档 contract/binding/evaluated_at/max_age/market ID，不由当前默认值重解释。 |
| EVG-004 / D2 | 旧 writer 与只读重开：先固定合并基线与精确旧二进制矩阵。逐一覆盖构造器、只读 opener、takeover、直接 order/fill/ledger/credit 金融入口及已有句柄；枚举 control lease 允许副作用。配置字符串比较不替代 fencing/capability。 |
| EVG-005 / D2 | 估值时间与最终行情准入时点：同一 captured now 用于参考/候选及同一决策快照，不能因此省略原行情准入和 precommit guard。实现须明确 logical valuation time 与最终准入 freshness/deadline 的适用时点，并归档所用政策；它不是物理 COMMIT 时间证明。 |
| EVG-006 / D2_D3 | shadow 失败与必须结算恢复：区分 candidate 数值差异/超域、candidate binding 缺失、reference binding 不可信。操作类别来自可信结算义务/调用链而非客户 flag。具体定义 candidate 失败时的 reference-only 结算、查询和重启 opener/audit/replay 路径，避免全局 strict opener 或共同 fingerprint 在写账前再次挡住已确认义务。 |
| EVG-007 / D2 | 金融回滚、冻结与结果未知：在明确的单写者/事务顺序中关联失败命令、金融回滚和持久 freeze，定义故障窗口；不能回滚一切后仅靠内存 flag 冻结，也不能让并发/重启命令在 freeze 落盘前继续新增风险。 |
| EVG-008 / D1_D4 | 独立证据、性能与权限边界：每阶段固定新 source/plan/argv/corpus/runtime。mutation 负例、纯数值、金融 SQL、撮合、容量分开；独立参考不调用生产 core；新 binding 序列化/双算成本单测量。 |

机器报告为 [review-53acece.json](../evidence/designs/cross-engine-binding-independent-verification/review-53acece.json)，包含每项反例、通过条件和原文位置。

其中有三条不能在 D2 被一句规则代替。首先，持久 binding ID 必须跨可信重启可重现，实际对象身份检查仍在每个进程中成立，不能把内存地址当历史ID。其次，一次valuation now有助于参考/候选精确比较，但不能悄悄取消最终行情准入或截止检查；实现必须明确其时点和回放含义。最后，candidate-only失败后的严格构造器/opener/audit/replay都要有已定义的必要结算恢复路径，否则应遵守原设计的只读/离线shadow回退门槛；参考本身不可信时应保留义务等待受审恢复，不能虚构结算成功。

同样，金融事务回滚后持久freeze的崩溃窗口必须有具体协议与故障测试。操作者或客户自行提交的“mandatory”标志不能成为绕过新风险检查的能力。这是需要实现验证的接口/事务约束，本审查没有执行任何反例或声称其在现有代码中已经失败。

建议继续完成固定合并基线与D1有界实现，再由另一组审代码和新资源计划。D2金融写入、旧二进制失效、历史重放、必要结算恢复及更高阶段仍保持未验收；真实资金必须另有独立审查和明确上线批准。回滚本审查只移除两个审查文件，不修改任何运行时、策略、历史账务或已有证据。
