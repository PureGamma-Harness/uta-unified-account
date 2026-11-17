# Managed 新借款的受信 owner 边界

本补丁收紧受信本地金融 owner 接口，不增加客户借贷产品。普通 managed HTTP 新借款
原本已返回 `501 unsupported_durable_operation`；反例没有越过这一客户路由、签名或
账户权限。当前 schema3 的完整决策审计仅覆盖订单接纳及线性确认成交，其 capability
明确把 `new credit decisions` 列为未捕获。不能据此授予 managed 新借款。

## 原始事实与修复

在 A1 `1c14441` 的真实 SQLite authority 上安装 schema3，再启用 persistent fence 并
取得真实仍活 token。受信同 PID owner 的 public borrow 和新 joined helper 都实际提交
了另一笔 BTC .1：账户现金/本金 .1→.2、pool .9→.8、journal 4→5，credit command 与
borrow event 各 1→2，但 `uta_risk_decisions` 仍为 0。两个红断言均在实际事务返回后执行，
不是在 rollback 中观察到临时数据。三个控制测试通过。原完整[红日志](../evidence/runs/managed-credit-boundary/original-managed-owner-red-python312.txt)
及运行时/测试 hash 保留，不把它说成普通客户可调用的漏洞。

修复在原 canonical credit replay 之后，通过当前事务读取真实 persistent writer-fence
authority。只要 authority 已 managed，新的 public/private borrow 都返回
`501 unsupported_credit_operation`；没有 cash/debt/version/ledger/event/成功 credit
receipt 副作用。不以对象上的 `managed` 布尔值、进程内缓存或调用者提供的 capability
开关授权。输入检查仍在 public 开 storage 前执行；原 ID、同内容的已确认借款先返回
原 receipt，原 ID 异内容仍 409 conflict。过期行情和 halt 不会让历史成功记录消失。

这不是新的 SQL 级操作识别或 retroactive binary 格式门禁。原 SQL guard 仍校验真实
financial role、PID/token/generation/nonce/lease 及 transaction-end fence；新的代码拒绝
不赋予旧二进制任何新权限。可信 OS owner 能运行旧实现或任意 SQL 的风险不由此补丁
消除；部署必须停止旧写者并通过原 fencing 协议交给固定新 artifact，禁止为了恢复新借款
而降级绕过这一政策。未来真正启用借贷仍需新显式格式能力和完整 audit，不能删除本判断
或把历史 `risk_evidence` 当作资格证明。

seal 前既有受测 bootstrap、显式资金证明、loan LTV 与 gross 账务规则原样。seal 后既存
债务的同币还款仍在 halt/断价时可执行，利息先于本金；该补丁没有增加自动借币、利率
调度、兑币清算或新的跨片额度行为。

## 验证及兼容性

三运行时各 **113 项**针对性测试通过：3.12 9.064s、3.10 9.906s、3.13 9.790s，零失败、
错误或跳过。3.13 使用 `-W error::ResourceWarning`，这些日志未观察到该警告。范围含
原信用/Cross/gross/监督/fencing、原 durable command/reference 和新 managed 边界。
它不是冻结源码的全量测试、安装包、容量或长稳验收。

三个原还款夹具曾在 managed seal 后制造贷款。`tests/test_durable_commands.py` 的两个
还款案例及 `tests/test_durable_reference.py` 的一个案例，现在把完全相同金额/CID 的源
贷款放到 fence 前的显式 bootstrap。原还款金额、利息优先、cash/debt、幂等和失败回滚
断言保留；没有用“新借款被拒绝”替代这些原金融断言。

joined helper 不拥有调用方的业务 savepoint。另一个真实反例在兼容风险模式的无抵押
账户上先执行 loan postings/debt，再由 projected risk 报 insufficient_margin；测试先
核实 staged cash/debt 确已变化，然后用实际 `ROLLBACK TO` 清除它们，提交一个 REJECTED
测试 receipt。重开后原 loan/CID 无成功、journal 只有 pool funding，补足抵押后原 CID
才可成功。未来 dispatcher 必须保留此逐命令 savepoint/rollback 责任，不能 catch 业务
异常后直接提交部分贷款。

无需数据迁移或 DDL。上线前 halt、drain、停止并失效旧 owner，保留全部原 CID、资金
与 nonce 水位，使用经独立验收的固定 artifact 恢复；先核对后激活。回滚优先前滚修复，
不能删除债务、回退 generation 或以旧软件解除本拒绝。后续门槛与全局预算方案见
[借贷前置计划](managed-credit-admission-plan.md)。`production_approved=false`。
