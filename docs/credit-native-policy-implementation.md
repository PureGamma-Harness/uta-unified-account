# Native credit policy：第一实现切片

基线 `aa72a953`，独立 M3 分支 `feat/credit-native-integration`。新增
`uta.credit_policy` 是生产用的有界、精确、无存储副作用证书解析器，**不是授信或激活接口**。
它只接受 synthetic `NATIVE_PREPARED` 与显式零新利率/零借款费/require-inbox/batch0
政策，拒绝 ACTIVE、production批准、verified等未声明字段。无cap旧运行模块未改。

输入为JSON文本或普通dict，拒绝重复键、float/NaN/Infinity、自定义对象、递归/过大树及
未知字段。元数据整数拒绝bool，金额只接受原币canonical ASCII整数最小单位字符串，
`0 <= units < 10^38`，不经float、Decimal上下文或SQLite整数CAST。scale与资产身份显式。

完整预算证书必须列出连续、唯一的全部authority/shard，所有credit资产的所有片分配，
每片opening本金、利息、pool及唯一资金claim。逐资产Σallocation<=global，opening
principal+interest<=allocation；资金claim总和须覆盖opening pool并保持账本数量范围。
不要求pool总额等于授信预算，也不把principal/interest与现金净额化。source_reference全
证书唯一，同片pool command ID不能跨资产重复，声明claim不等于外部到账证明。

policy/certificate/descriptor/allocation使用规范内容ID。提供的expected authority、layout、
shard、scale、policy、certificate及authority set逐项绑定；即使攻击输入重算全部hash也
不能满足已封存的外部expected身份。无状态解析器不能单独证明UNKNOWN额度未重新分配，
必须由native安装/load用原封存ID及真实持久ledger/source事实核验。返回对象冻结且没有
ready/verified权限，`stage`始终为NATIVE_PREPARED。

native组将使用真实authority generation0/owner=None/never-acquired条件，在同控制事务
核验实际opening及pool_funded记录后封存。第一能力阶段禁止acquire、READY、activation
和新金融成功，不使用虚构decision或wrapper来解锁。完整credit UDF/实际执行上下文、
审计/source/replay尚在实施；公开借款仍501，真实金融签字与贷款清算缺口不变。

首轮12项纯函数测试通过（原始输出、精确源摘要见
[证据](../evidence/runs/credit-native-policy-initial/manifest.json)）。这些测试不是SQL、native
门禁、冻结完整运行时或生产验收。独立金融组在读取本实现前已提交自己的参考语料，将
另行对本wire和实际native安装差分，拥有否决权。

本模块没有部署或数据迁移；未接入现有CLI/路由/运行中的source。下一native代码切片
在独立临时authority验证；不能把本模块的结构校验结果直接拿来授予资金权限。
