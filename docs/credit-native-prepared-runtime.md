# Native credit format1：只准备、不授权交易

本切片提供实际默认关闭的 `uta/credit_native.py` 与 writer-fence 集成，依赖已审
`credit_policy.py`。只有显式 `prepare_credit_native` 调用才安装任何新对象；普通 base/
batch 路径不创建 credit schema。当前 format1 的唯一状态是 **NATIVE_PREPARED**，没有
激活或解除方法，不能取得金融 owner、READY 或成功新增信用。完整信用交易仍 NO-GO。

`prepare_credit_native(Database(...), raw_descriptor)` 只接受真实 generation0、owner空、
从未 acquired/renewed/released 的已托管 authority；有过 owner 后不可用本方法 promotion。
descriptor 由真实预算模块按当前 authority 和 ledger asset scales 重验，实际 principal/
interest/pool 及逐条 pool_funded source/CID/数量在同控制事务核对。只保存规范证书、政策、
本片分配及 opening legacy 摘要，不将其他片或外部托管声明说成已核实到账。

固定 schema、复合 UNIQUE/FK、immutable/no-replace guards、writer guards、reserved marker
及 `credit_native_prepared_v1` event 在同一 SQLite 控制事务提交。仅编译入的对象名能走
内部控制安装器，不接受任意SQL。重复同 descriptor 只验证，冲突或损坏拒绝，不自动修复。
base/batch/credit/both inventory 显式列举；缺失已声明的 marker/event/schema 失败关闭。

准备态的 `acquire`、`assert_writer` 与所有金融/producer DML/DDL 返回 `credit_not_active`。
原生 `uta_credit_operation_v1` 是实际注册的拒绝函数，不能提供成功作用域；调用被捕获后
guard仍中止提交。DROP/ALTER native保护在authorizer当场拒绝。控制角色也仅能使用原有
受控对象，不能转写credit元数据。没有以测试伪造 READY、token、完整审计或成功回调解锁。

操作 intent、实际staged intent EXISTS、postings集合和credit-record closing-point的固定
SQL外壳已安装，但**它们在本格式下从不授予正向金融权限**。完整typed operation/context、
实际信用artifact/operation replay、source/HMAC、交易预算扣减及终末风险检查仍需下一
独立审阅格式；不能凭这套预备schema声称完整NC-01–09或借款链路已验收。没有修改
credit.py、CLI、订单路由、长稳源码或已有authority。

部署仅限新的私有合成authority：完整离线bootstrap/对账→enable原fence（尚无owner）→
显式准备。prepare之后保持关闭，不能试图启动交易worker或降级。多片全局计划、READY
移交及上线审批不由此单库方法完成。失败保留原库和证据按review前滚；不能删marker、
退generation或用旧备份覆盖新资金。合成单测只能清理它自行创建的临时目录。

首份实际验证固定 `c33abf1109d925960e2c6dc12100bbd2e3630fef`（含完整M2祖先8338与
实际policy模块），CPU4在2026-11-17 11:24:25.982717–11:24:28.528445 UTC执行。14项
专项通过，unittest2.241秒，实际进程2.545733秒，零skip。包括真owner与prepare竞争、
无cap金融COMMIT、opening利息、实际DDL拒绝/捕获后的fatal、准备态无owner/作用域、
中断回滚与不修复、旧458四组合及旧ad3写入拒绝。完整[原日志及源hash](../evidence/runs/credit-native-c33abf1/manifest.json)
保留；它只证明此准备切片，不证明逐借款正向native操作已完成。

普通base/batch语义的更广回归、新增cap事件检查的开销审查及独立peer review尚待完成。
后续源码需另行记录，不把这一14项通过迁移到新SHA。生产、真实资金、持续容量和复制
RPO/RTO均为未验。

## Fresh事件前缀与默认路径

后续独立修订将fresh history明确固定为`[(1,enabled_guard_v1)]`，或先启用batch后的
`[(1,enabled_guard_v1),(2,batches_enabled)]`，任意额外control事件也拒绝prepare。因此
本format的prepared事件只能位于seq2或3；load在固定前三条中检查信用事件，并要求
prepared库没有后继事件。旧base/batch的guard/event查询逻辑保留，避免为缺省未启用信用
的batch库增加整个renewal历史扫描。这是静态路径/正确性修订，不是性能验收。

该证明依赖实际安装器对fresh历史的严格限制；它不是恶意OS/control历史任意改写后的
外部反回滚证明。缺少已声明marker或schema仍失败关闭，不通过删event降低保护。

修订源码`20af9cc413fd431f502ba1f467e5efd7040fb336`的122项专项在CPU4全部通过，
UTC2026-11-17 11:33:57.656508–11:34:14.844764，unittest16.830秒、进程17.188264秒。
范围含native16、原writer fence/旧binary、credit/join/gross/A2边界、durable batch及
policy；零skip/timeout。[原始结果](../evidence/runs/credit-native-20af9cc/manifest-python312.json)
不替代后续金融源核验修订、三运行时完整验收或性能结果。

## 不可逆准备前的完整金融源校验

后续单独修订在同一原control W事务中，使用本地固定只读view调用原
`DurableLedger.verify(connection=...)` 和 `CreditService._verify(...)`。不运行服务/账本
schema构造器，不起第二个事务、伪造startup context、verified flag或writer token，不
返回或缓存view。view只提供原核验需要的读取和codec方法，没有posting、借还款或
`_transaction`接口。任一原核验异常固定为`credit_financial_source_invalid`，内部保留
cause，外部消息不包含SQL/nonce。

完整journal/hash/逐币projection、逐账户principal/interest及信用记录检查通过之后才
做本地opening/claim核对，再开始第一个native DDL/marker。聚合数相等不能掩盖某账户
负本金与另一账户正本金抵消、债务与liability ledger不符或pool projection脱离journal。
新增负例从enable前真实损坏source开始，要求金融原始字段/SQL及generation不变、没有
native对象；不声称WAL/SHM物理字节不产生正常SQLite变化。实际结果另记，不预填通过。

固定源码`26f7c59ec66f4553fcd135816509f02a00550de7`实际执行native17+policy12，共29项：
Python3.12为3.248秒，3.10为2.720秒，3.13为3.026秒，三份均通过、零skip；3.13将
ResourceWarning提升为错误，三份raw未观察到该警告。完整[原始日志与运行时](../evidence/runs/credit-native-26f7c59/manifest.json)
及前述旧14/122结果分开保留。四种真实损坏source均在marker前以固定源错误拒绝，原SQL/
金融字段及generation不变。此专项不能充当完整发布验收或新增信用许可；独立peer与
完整正向credit audit/source/replay/操作阶段仍未完成，格式1依然不能交易。
