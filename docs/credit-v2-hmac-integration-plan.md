# HMAC 借贷来源与 CreditV2 接入方案 v1（仅设计）

本方案以 `dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b` 和 PR18 的 `01c332375d9a5463ca95d8e743ff5083b121982e` 为事实边界。**尚未实现接入，不能启用客户借贷、READY 或真实资金。** 当前正式候选只修 Python3.10 测试夹具；本方案不向其混入运行时代码。完整输入 SHA256、提议格式、权限、事务、分期和 30 个未运行的验收案例见 [机器可读契约](contracts/credit-v2-hmac-bridge-v1.json)。

## 已验证的代码事实和缺口

| 事实 | 原代码位置 | 对接约束 |
| --- | --- | --- |
| 实际认证库为 `NonceStore`，没有名为 `AuthStore` 的实现 | `uta/request_signing.py:188` | 文档中的 AuthStore 泛指此库；不得制造另一个假认证实现 |
| `NonceStore.consume` 在独立 WAL/FULL 事务中写 nonce/audit，成功后返回 None；`authenticate` 只返回 Credential | `request_signing.py:287,344` | 当前不能提供原子接受的审计序列、profile revision、grant epoch；不能从稍后 profile 读取或捕获时间推断 |
| PR18 `CreditHmacSource.issue` 调用真实认证，仅允许 funding + 精确 key/account 本地 grant | `credit_hmac_source.py:155`，PR18 | 只签候选证据；audit/epoch 字段为 null，financial_authorized=false，revocation_barrier=NO_GO |
| PR18 receipt 只在进程内按对象身份、实际 Thread 对象、PID/boot 绑定 | PR18 源及独立报告 | 重启后不保有 first-CID 知识，导出的 JSON 不能导入为授权对象 |
| 现有 HTTP `_SignedDurableHandler._principal` 已读取原始 body 并消耗 nonce | `durable_gateway.py:353` | 路由再调用 PR18 issue 会第二次认证并触发 nonce replay；必须一次认证产生真实服务内上下文 |
| `_permit` 给 admin 隐式通行；现有 funding 的 command query 只允许 REPAY | `gateway.py:333`；`durable_gateway.py:268` | 借贷和借贷查询使用独立精确授权检查；不能直接复用这两个宽/窄规则 |
| V2 marker、source CHECK、parser、native guard、artifact/audit 都绑定 format2 / synthetic_local | `credit_native_v2.py:26,63,834,926,1305` | 修改 source_kind 字符串或字段集合就不是已验收 V2；不能把 HMAC 数据重标为合成来源 |
| V2 source+PENDING 已是同一 producer COMMIT，金融 intent/effects/decision/journal/terminal 是后一个 COMMIT | `credit_fifo_v2.py:163,225` | 保留两个边界，不能宣称认证库和金融库三个提交是原子事务 |
| 跨 epoch 原 CID 目录、retirement-aware reader 和认证切换屏障只有设计 | `credit-authority-upgrade-boundary-addendum.md` | 新物理 DB 的本地 miss 不是新业务证明；当前禁止带未决请求切换或借旧 CID 生成新债务 |

上表来自文件/Git/AST 阅读，没有运行认证、SQL、原生 guard、HTTP 或金融执行。PR18 原组件测试和独立审查只属于它原来的未接入范围，不等于客户 HMAC 借款通过。

## 本系统拟采用的范围和规则

下一运行时必须使用单独的 **fresh HMAC_CREDIT3** 能力及 source format3 / `hmac_authenticated_v1`，名称在这里仅作设计保留。旧 V1 PREPARED 与 V2 synthetic authority 保持原格式，禁止在线补表、改 marker、放开 source CHECK 或通过别名冒充新能力。安装前必须逐个验证旧二进制无法取得新 authority 的 owner 或提交金融写入；只增加新 marker 并不足以证明旧代码会拒绝。

最初仅一租户、一账户、一分片；BTC 借还、USD 风险计价、scale8、零费率/零利率、batch0/cache0。保留现有 Cross 参考模型的 gross assets、cash deficit、本金和利息分量。借款仍需真实市场 SID、两次报价/风险检查和完整四腿；还款沿原利息优先规则保存四/七腿，不需要新借款 quote，必须能在 halt/行情过期时按权限还款。本方案不覆盖订单、清算、利息调度、保险基金、ADL、多结算币或生产 PM。

现有 Credential 没有 borrower role，第一期不扩展全局 role 枚举：借款要求实际 `funding` role 加持久的精确 `credit.borrow` grant；还款要求独立的 `credit.repay` grant。grant 绑定 key/account/asset/operation/epoch。admin/risk/trader/reader 没有隐式借款许可。查询要求当前有效的 reader 或 funding 加 `credit.read` grant；提交过借款的已撤销 key 没有永久查询权。客户还款不依赖原借款 key 或 borrow grant 仍有效。

业务键固定为 `(domain_id, tenant_namespace, account_id, business_CID)`，不包含 epoch、source transport ID、操作类型或 payload hash。改变操作类型/内容对原键产生 409；切换 epoch 不能逃避去重。现有物理 inbox 的 command_id 全局唯一，因此本小范围先明确只允许一个账户；未来多账户的物理映射必须单独规格化，不能悄悄重命名客户 CID 或以 replacement CID 规避历史。

## 最小事务协议及撤销候选机制

本节是需要实际故障验证的提议，不是现有保证。保持以下独立提交：

1. **T_A，NonceStore AuthDB**：真实 MAC 验证后，在一个事务里检查当前 key/grant、nonce/时间窗口，记录实际 audit sequence、profile revision、key identity、grant epoch，并保留 accepted receipt 与原始业务 reservation。有效签名但输入/角色/grant 拒绝时，按明确策略保留 nonce 与 denial audit，不生成 accepted receipt/source。只从事务实际返回后签发进程内 opaque handle；异常或回复丢失不能签发成功对象。
2. **T_P，金融 producer**：先查完整原业务目录及原 CID。只有完整已知 absence 和同键 reservation 成功后，才能把原 authenticated source 与 PENDING 一起提交。已存在同业务 PENDING/terminal 返回原状态；缺失历史 source 不回填。AuthDB reservation 与金融 producer 不是一个 COMMIT；未知交付必须保留原 reservation 并查询原 CID。已有 AUTH_RESERVED 且原金融 producer 已确认 absence 时，只能继续交付这一份原接受记录，不再创建第二个 reservation/source 候选；producer 结果 unknown 时只能查询和协调原交付。
3. **T_E_AUTH → T_F，执行候选屏障**：同一 executor PID/Thread 先取得 AuthDB `BEGIN IMMEDIATE`，检查实际已提交接受记录、当前 key/grant/revision/epoch，然后在持有该事务期间取得金融事务并提交或回滚。所有 key/profile/grant 撤销也必须通过同一 AuthDB 写事务。这样如果撤销先 COMMIT，执行见到无效权限并拒绝；如果执行先持锁，撤销不能在金融 COMMIT/ROLLBACK 之前确认。全局顺序恒为 AuthDB → 金融 DB；任何反向拿锁路径都不在支持范围内。
4. **金融 T_F**：真实 native context 绑定上述实际 AuthDB guard、原 acceptance/source/CID、当前 grant snapshot、actual account/FIFO/market 和 owner token。保持原金融 intent/effects/journal/decision/credit receipt/terminal 同一 COMMIT。native closing gate 再检查真实 guard 未关闭、仍在原 PID/Thread/authority 的事务中及权限/时间边界；被捕获的 gate 错误也必须使 COMMIT 失败。不得仅接受一个 caller-supplied bool、dataclass 或权限 epoch 数字。
5. **T_O，AuthDB 观察记录**：金融结果已知后可追加原 financial receipt 引用并提交 AuthDB 事务；此观察提交不是金融 COMMIT 的一部分。若金融成功但 T_O/HTTP 回执丢失，原金融 terminal 仍有效，恢复先查它，不能重做债务。金融记录只依赖已提交的 T_A 接受记录；不得为未提交/可能丢失的 T_O 设计跨库 FK，或因为缺 T_O 而冲掉已提交贷款。

锁顺序还包括现有 authenticator RLock：`replace_profile` 先持该锁再写 AuthDB，所以 executor 在持 AuthDB 时不得再次取 authenticator 的 profile 锁，也不得调用 `authenticate`、`consume` 或构造会 configure 的 authenticator。fresh AuthDB 应保留与 key identity 绑定的非秘密 role/account/not_before/expires 元数据；执行只读同一已持有连接的实际行，不能从可变内存 profile 补证据。全局 profile revision 上升不自动撤销未变化 key；检查当前原 key identity、永久 revoked 状态及原 grant epoch 是否仍有效，不能将一次无关 key 轮换误判为原账户撤销。新 epoch 的重新授权不复活已撤销原 grant/CID。

禁止远程异步金融 worker 在持锁进程之外继续执行：auth owner 崩溃释放锁后，独立 worker 若还能提交，就会重新产生 revoke/execute 竞态。初版只允许同进程同线程拥有两套事务。现有进程 fencing、native guard 及启动工厂都必须认识此能力；旧普通 worker 不自动取得 HMAC 执行许可。

这是单机两 SQLite 权威之间的串行排序候选，**没有分布式原子提交**。持 AuthDB 写锁跨完整金融事务会阻塞其他 nonce/profile 操作；它目前没有容量资格，不能宣传为万笔/秒架构。多节点使用需另一个可验证权限/执行排序协议，本方案不把锁延伸成未经实现的 HA 声明。

时间规则独立说明：key 有效期在实际 auth checkpoint、金融选择和 native last-check 检查，等于 expires_at 的边界拒绝。撤销先后按上述事务排序，不能按两台机器的 UTC 比较判定。auth server_ms 是锁内真实检查时刻；producer accepted_at 是金融 producer 的真实时间。两者都不是物理 COMMIT 时间，physical_commit_at 继续 null。行记录本身不能证明历史上真的持有跨库锁；需代码约束、实际竞争/故障证据和独立审查共同验证。

## 具体改动边界和提交次序

| 阶段 | 预计改动位置 | 可独立交付的最小行为 | 仍拒绝 |
| --- | --- | --- | --- |
| H0 | request_signing 的共享认证核心；新增 credit_hmac_ingress | fresh versioned AuthDB 的真实接受 receipt、durable exact grants、一次 MAC/nonce；现有 authenticate 的返回契约保留 | 金融 source、执行、listener、public borrow、READY |
| H1 | 新 credit_hmac_native / credit_hmac_fifo；writer_fence / existing_services 的独立格式分支 | fresh HMAC3 的 source+PENDING 和 original-CID 查询/交付，actual authoritative AuthDB 记录可交叉核验 | 金融贷款/还款执行及普通交易 |
| H2 | 新 native closing/credit audit/replay/artifact manifest | 同 PID 双事务排序、实际 BORROW/REPAY、回复丢失/重启恢复 | 公共路由、生产、跨账户/分片、旧 authority 升级 |
| H3 | 新 credit_hmac_gateway；只提取既有有界 framing/TLS 复用点 | 独立 opt-in loopback TLS handler，借/还/查一次真实认证，default gateway 仍501 | Bearer fallback、无TLS、默认启用、生产流量 |
| H4 | 独立 oracle/故障组/QA/包/注册压测 | 新源完整验收；每个版本单独的原始结果和失败保留 | 任何未实际过门槛的生产/容量声明 |

PR18 原 candidate-v1 仍按其历史契约保持未接入，不能把 financial_authorized=false 改成 true 来冒充 H0/H1。新接入复用它已审查的严格输入、冻结 headers 和 opaque 身份边界，但使用真实 accepted-receipt API；REPAY 的 signed path/kind 是新的显式范围，不能假称 PR18 原 borrow-only parser 已支持它。

H0 不应复制第二份 MAC/时间/nonce 核心；新增 typed receipt API 和现有 `authenticate` 共享同一实际检查路径。role/grant/business 拒绝必须有明确 nonce 是否已消费及原始审计语义；未知返回不伪造 receipt。H1/H2 不得直接改 V2 parser 让其接受另一 source_kind。新的金融能力及 code artifact 必须包含实际新增 runtime，完整校验 native inventory、source/audit/factory/reader 代码与 schema。

HTTP 不能在已经调用 `authenticate` 后再调用 PR18 `issue`。H3 的真实认证入口一次返回 principal 和仅在本请求线程有效的私有上下文；route 使用它，不接受客户端 JSON principal 或导出的 receipt。借款 body 是严格的 command_id/asset/amount，签原始 exact method/path/body。还款使用单独签名路径和 operation grant。拟定独立 query path `/v2/accounts/{account}/credit/commands/{cid}`，避免现有 funding-only-REPAY 查询规则无意隐藏借款，亦避免放开其他业务查询权限。每个路径均先验证当前查询凭据，不因查得到原 CID 就授予权限。

## 拒绝与重试契约（均待实现）

| 条件 | 拟定结果 | 资金/来源要求 |
| --- | --- | --- |
| 未启用新能力或旧普通 gateway | 501 unsupported credit operation | 不创建 AuthDB/marker/source，不改变 READY |
| MAC/body binding/tenant/audience 不符 | 401 | 无金融 source/效果 |
| 实际 funding 但没有 exact grant；admin 请求借款 | 403 | 已认证 nonce 可消耗并审计，不能变成借贷许可 |
| 非规范 JSON/金额/字段 | 400 | 无业务接受；有效 MAC 的拒绝 nonce/audit 策略需 H0 实测 |
| 已有逻辑 CID、kind/payload 不符 | 409 idempotency conflict | 原 source/terminal 不变 |
| 已确认原同业务 PENDING 或 terminal | 202 原 PENDING /200 原 terminal | 无新 source/loan/journal；ack 不等于风险接受 |
| 认证/source/金融 COMMIT 回复丢失 | 503 outcome unknown | 不换 CID、不从异常推断失败/absence；新 nonce + 当前 query grant 查原 CID |
| 撤销先提交或 grant 确认无效 | 原 source 的 REJECTED403 | 无金融效果；不能把新 key 接到旧 source 复活贷款 |
| auth/目录/来源不可用或 unknown | 503 / PENDING | 不释放原 reservation/预算，不换 shard，不绕过 gate |
| 无历史 source 的旧 receipt | 授权查询原 receipt 或 typed拒绝 | 不制造历史 HMAC 接受或新效果 |
| key 只在历史有效、现在已撤销 | 拒绝新请求/查询 | 已提交贷款及原审计不擦除，另一个当前授权 key 可查/还 |

## 真实验收计划及当前授权

机器契约 HC-01..HC-30 均为 **NOT_RUN**。包括真实 TLS/HMAC 一次 nonce、精确角色/范围、opaque forgery、AuthDB COMMIT 后回复丢失、source COMMIT 后重试、实际双进程 revoke/execute 竞争、guard 关闭后捕获异常仍 COMMIT 失败、金融 COMMIT 后 AuthDB observation 丢失、进程退出重开、借还资金守恒、行情中断时还款、旧二进制 positive-control/新格式拒绝和独立两库对账。每项须保存 source SHA、实际参数、命令、CPU、时间、exit/stdout/stderr；失败和 unknown 不覆盖重跑。

本轮授权只有阅读、Git/AST/哈希和纯内存 JSON 契约校验。**没有运行 SQL、打开 DB、导入产品代码、启动 TLS/listener/native/bench、打包安装或 push。** 各阶段必须先由集成负责人审查具体 diff 并给出该阶段范围。建议下一 H0 仅新建私有 AuthDB 的短组件测试，CPU3/4 由 root 分配，每批上限30秒；H1/H2/H3 提议每批60秒，TLS 只127.0.0.1临时端口及自生证书。这些是未来建议参数，不是本轮执行授权。

## 部署、恢复和回滚

目前只有文档，无部署、DB migration 或回滚命令。未来各阶段默认关闭，并先证明 fresh-only 安装失败全回滚、旧代码拒绝及审计可重开。T_A 已接受但 T_P 未提交/未知的请求进入 pending delivery/reconciliation 集合；TTL/lease 过期不使它们消失。T_F 结果未知先由当前授权查询查原 CID，已提交结果永久保留。对账 joins AuthDB accepted receipt/audit → 原 source/PENDING → intent/decision/credit/journal/terminal，所有重复身份与金额要一致；T_O 缺失作为待补观察，不伪造金融失败。

在新 authority 已有真实金融效果后，回滚采用保留原 source/CID/ledger 的前向修复；禁止删除能力 marker、把 HMAC3 数据交给 V2、回滚财政状态或重放成新贷款。跨 epoch 全球目录、退役可读路径和 AuthDB 未交付 grant drain 未实现，因此本小范围拒绝在线升级。单机 WAL/FULL 不覆盖磁盘丢失、多可用区或更大故障，不宣称 HA/RPO0；参数/容量与生产审批均保持未通过。

公开材料只放合成测试 ID、实际状态、非敏感计数及白名单哈希。认证私有 DB、金融 DB、密钥文件、TLS 私钥、原 live nonce、签名和含它们的请求不进入 Git。真实执行的原始私有证据可保留在批准目录，公开 stdout/stderr 必须由明确 allowlist 产生，而不是事后正则掩盖秘密。
