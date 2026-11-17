# Existing-only service construction：最小实现切片

基线为root提交`402ddeb`，本分支`feat/credit-existing-readonly`，先cherry-pick真实read/control
join helper原OWN`cf4e331de5b092b0a8ec3d84b6efe3bc2d121a4c`（本分支`143fe60`）。
本提交作者负责factory/constructor接缝，**不是本功能的独立验收签字或V2 restart READY**。

```python
services = open_existing_services(database, clock=clock)
# 或在确切原Database对象的真实read/control事务内：
services = open_existing_services(database, clock=clock, connection=connection)
```

返回真实`ExistingServices(exchange, credit, ledger)`；exchange/credit/ledger均使用原公共
`__init__` common参数校验、真实Ledger codec及相同Database对象，不用`__new__`、假
`_OwnedStartup`、verified flag、actor字段或caller verifier。未传connection只开一个实际
`Database.read_transaction`；传入connection必须由原registry验证同DB/connection、read或
control、线程、active transaction、未poison及实际已绑定token。financial/inbox/raw或仅
同路径的另一Database不能变成constructor read join。

三个公共constructor新增私有`_existing_connection`参数，None时保留原默认/owned-startup
路径。existing分支不执行`_claim_authority`、`_schema`、audit.install或任何DDL/INSERT/
迁移/修复，而是在同连接完成：

- 原ledger fixed schema/guards、scale与完整`DurableLedger.verify(connection=...)`；
- 原trading fixed table/constraint/index/guard、exchange authority、schema2或3、fee累计列；
- 原完整credit schema/guards/唯一funding index和`CreditService._verify(connection)`；
- 原persisted policy/risk_policy/halt值精确匹配，配置模型仍由真实ProductCatalog/
  PortfolioRules及公共constructor校验；
- schema3的实际base audit能力/guards/表/FK和decision link列，唯一匹配的真实archived
  policy（含cache options及fee Decimal表示），以及**当前实际build的base artifact必须已存**。
  缺current artifact不写入；多个匹配archive时因缺active-policy指针而拒绝，不猜“最近”。

schema2 legacy source可按真实持久配置恢复cache0，保留原无audit声明。schema1或缺fee列
只能走另外的显式离线迁移，factory不补。返回对象不保存constructor connection，也不
代表未来时刻source/lease仍有效；后续操作仍执行真实Database/native fencing。

expected SQL来自固定编译定义，没有创建scratch数据库生成“官方schema”。14条trading
SQL仅纯抽出`_schema_statements()`，逐字符串与899c相同。table/index按严格SQL token及
PRAGMA列核对，所有约束保留；只重现SQLite标准ADD COLUMN把新列放在table constraints
之前的重写。trigger定义仍精确比较。未知额外index/trigger不能暗中加约束，只有原实际
`_load`/full native验证后的compiled auxiliary定义及固定audit/writer guards可以出现。
schema expected数据按调用局部构造，无可变全局schema/verified cache。

当前最小能力覆盖真实unmanaged/base及现有已加载format1辅助对象。未来format2完整
inventory、native token获得、source/FIFO/lease接缝与rebinder仍由native/root另审；这里
不伪造V2 owner、READY、source或新金融成功。建议实际合法token获得后用
`database.for_writer(token)`再调用本factory创建**新**对象组；不修改旧bootstrap对象的DB
字段，也不简单赋actor字段。binder和真实V2恢复尚未由本提交验证。

作者首微批CPU3，ResourceWarning升为错误，真实临时Exchange/Credit source：

- 首9项：6项成功，3个positive在本组新checker的标准ALTER列位置错误处失败。首raw
  保存在`first-python312.json`，没有覆写。实际public constructor产生的SQL诊断另存，
  不是scratch假authority或隐藏生产源损坏。
- 仅修本组checker为顶层column/tableConstraint分段后，定向3项positive通过：普通read、
  真base control、schema3 current artifact与原cache7/2及Decimal fee表示恢复。
  实际进程0.306秒，没有重跑原helper矩阵。
- 首次missing-guard泛StorageError可能被较早checker错误遮蔽，因此额外仅加强并重跑该
  1项，明确错误为缺`credit_commands_no_update`，实际0.291秒，无修复且logical snapshot
  不变；没有将错误阶段当作guard拒绝通过。
- AST证据：三个默认constructor删除仅新参数/分支后与原相同；原14SQL字符串byte相同；
  `_borrow/_repay`、public borrow/repay、原credit verify/schema及service risk/fill/order/
  authority方法AST未变。未触借还款金融逻辑、CLI或默认路由。

完整begin/end、实际命令/退出码、各次source hash、SQL诊断和AST检查见
[作者原始记录](../evidence/runs/existing-services-construction/)。这些是作者microtests，尚
缺后续完整negative矩阵、默认路径更广回归和独立PM验收，不能迁移成production许可。

readonly指constructor没有logical schema/row写入；真实SQLite打开/事务可能涉及正常DB/
WAL/SHM活动，不声明底层文件byte完全不变。未改任何existing/live authority或原baseline。
本切片无迁移/部署动作，回退代码即可，不能为真实cap降级或回滚已确认的资金水位。

## 后续作者negative矩阵

生产代码固定`bf746b1e7f5437f20fc1f953d7023b3d59615720`后，仅新增测试，未再改三核心
文件或factory。CPU3于2026-11-17 14:22:22.659362–14:22:23.266834 UTC执行12项新例，
全部通过：unittest0.484秒、实际进程0.607476秒、无skip，ResourceWarning为error。
没有重跑前面的helper或3个positive，也没有运行native V2/FIFO恢复。

使用真实public服务/credit构造的源库，随后显式腐化negative，并核特定拒绝phase与所有
logical schema/rows保持原坏源状态：missing file与whole credit module不创建；原列不变
但移除CHECK、额外CHECK及未知UNIQUE index拒绝；完整ledger拒pool projection脱离journal；
完整credit拒逐账户±本金抵消；缺当前artifact不写入回填；两个真实normal constructor
归档不同execution options时拒绝猜测。另核三个公共ctor均拒financial join，closed/raw
连接不能构造。约束负例从真实空orders表的原DDL重建为明确坏表并保留原index，未用
scratch SQL模型当作“官方schema”或正向source。

[新测试](../tests/test_existing_services_negative.py)与
[唯一实际批次raw](../evidence/runs/existing-services-construction/negative-first-python312.json)
单独保存。它们仍是代码作者检查，不代替独立PM验收、实际完整native V2/cap/source/
lease/FIFO或READY。后续完整credit artifact的loaded-role覆盖还需纳入新的factory helper
模块；本提交不自行扩张原base artifact或声明新授权。
