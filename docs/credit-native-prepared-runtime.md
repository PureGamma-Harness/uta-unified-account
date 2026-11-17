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

本提交先交可review代码，实际小规模测试结果另以固定源码和原始日志追加；不得预填
通过状态。生产、真实资金、持续容量、复制RPO/RTO均为未验。
