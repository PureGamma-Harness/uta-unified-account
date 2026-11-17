# H0 认证接受规范补充 v1：仅设计，禁止执行接入

本补充规范落实独立审查 `6063268d4da26f8b8b229c421775a3f96bb3e303` 的 H0-R1..R8。该完整 OWN 已在设计分支保留为 `c3aa351`。原 `431225d` 两个文件及 30 项 NOT_RUN 原样保留；本补充只在 H0 范围覆盖其中 nonce 消耗、retry handle、原 CID 查询、新认证库格式和配额的歧义。H1..H4、HMAC3 金融来源、跨库执行屏障和公开路由均没有实现或执行批准。

机器规范为 [credit-hmac-h0-contract-v1.json](contracts/credit-hmac-h0-contract-v1.json)，DDL 文本为 [credit-hmac-h0-schema-v2.sql.txt](contracts/credit-hmac-h0-schema-v2.sql.txt)。DDL **没有被 SQLite 解析或运行**，不能宣称 schema 正确或组件通过；其作用是让下一轮代码审查看到精确字段、FK/PK、CHECK 和不可替换保护。

## 当前允许与不允许

本轮只有代码/Git/AST/哈希阅读、文档与纯内存检查。没有产品 import、数据库打开、SQL/native、TLS/listener、金融 source/PENDING、全量测试、打包、基准、push 或 READY 修改。已冻结的909及其所有作业保持不动。后续若获批准，从 root 指定的 exact909 提交另开 sparse runtime/tests 分支，不在本设计分支或冻结目录实施。

H0 可提议的真实组件只有：fresh format2 AuthDB、共享的真实 MAC/nonce 核心、持久 exact grants、auth-only first acceptance、真实签名 AuthDB 原 CID lookup 和本地 opaque observation。BORROW/REPAY 在 H0 都只是认证意图观察；没有资金、借还、风险接纳、source 交付或撮合执行。每个导出记录的 `financial_authorized`、`source_delivery_authorized`、`execution_authorized` 必须为 literal false。

## 精确接口边界

| 拟定接口 | 输入与返回 | 必须保证 |
| --- | --- | --- |
| `CreditNonceStoreV2.initialize(path, *, tenant_id, producer_binding, domain_id, domain_epoch=1, account_id, limits)` | 显式离线新建一份私有 authority | 只接受不存在的目标；完整 format2 一次初始化；无 format1 repair/upgrade，无金融对象 |
| `CreditHmacIngressV2(auth_database, profile_path, *, tenant_id, producer_binding, domain_id, domain_epoch, account_id, enabled=False, max_handles=256, query_handle_reserve=32)` | 真实私有 AuthDB 路径及真实私有 profile 文件 | 未 literal enabled=True 在打开文件前501；无 caller principal/authenticator/SigningProfile/verifier/SQL callback 注入 |
| `capture(headers, *, method, request_target, body)` | POST exact `/v2/accounts/{account}/borrow` 或 `/repay`，严格 command_id/asset/amount | 一次真实 MAC、一次 AuthDB nonce 事务；新 CID 返回 auth_first_observation，已有同业务 CID 返回 auth_query_only，均在实际 COMMIT 正常返回后签发 |
| `lookup(headers, *, method, request_target, body=b'')` | GET exact `/v2/accounts/{account}/credit/commands/{cid}`，无 query、空 body | 当前 reader/funding + exact credit.read；真实新 nonce 与 query audit；只查 AuthDB 原 first acceptance |
| `inspect(handle)` / `release(handle)` | 本 issuer、PID、当前 Thread 对象的注册 opaque 对象 | 仅被动历史证据；不能导入 JSON/copy/fork/另一线程对象；release 仅释放本地 slot，不删 DB reservation |
| `replace_profile(profile_path)` | 真实 private loader；离线可信调用 | profile lock→AuthDB 的固定顺序；实际单调 revision 和永久 revoked；不自动生成 grants |
| `put_grant(grant_id, *, key_id, account_id, asset, operation, expected_grant_revision)` | 离线 exact-control API | 同一 AuthDB BEGIN IMMEDIATE、实际 key/role/scope、CAS revision、真实 audit/epoch；同 ID 不同内容409，不允许 active duplicate |
| `revoke_grant(grant_id, *, expected_grant_revision)` | 离线可信调用 | 原 grant 的永久 tombstone；已撤销返回原记录，不能以新 epoch 复活旧 CID |

以上路径只是组件的签名字节契约，H0 不安装 HTTP endpoint。H0 lookup 返回的 `found=false` 只说明本 AuthDB 没有 first acceptance，不能证明金融库、旧 epoch 或另一 authority 不存在命令。它不返回金融 PENDING/terminal，不等于订单或贷款查询。

`CreditNonceStoreV2` 不作为旧 `NonceStore` 的宽松子类进入旧 `RequestAuthenticator`。旧 `authenticate(headers, *, method, request_target, body)` 保持返回 Credential 及 format1 行为。共享私有真实 MAC/header 检查和 held-connection nonce/time/replay 核心，新 wrapper 只增加版本化业务结果与审计。不能复制第二份 MAC/时间窗口规则，也不能在 capture/lookup 之前调用旧 authenticate 消耗一次 nonce 再调用新路径。

## 确定的 nonce、审计和拒绝优先级

1. 未启用、本地 issuer/PID/handle slot 不可用：打开 AuthDB 前拒绝，无 nonce、无 DB 审计、无 handle。PID 必须在可能继承锁前检查。
2. 冻结 headers，检查 exact method/target/body 的签名框架并真实验证 MAC。重复 header、未知 key、坏 MAC、tenant/audience 不符或不能形成 canonical request：401，无 AuthDB 写入。有效签名但业务 JSON/path 不合法属于后面的业务拒绝。
3. 取得实际 AuthDB BEGIN IMMEDIATE，先校验 exact MAIN schema/authority。真实 clock 在拿锁后采样。复用单一 nonce 核心依次处理 highwater、strict expiry prune、当前 key identity/永久 revoked/有效期、请求时间窗口、replay 和有效配额。旧 format1 的原始优先级和返回语义不得改变。
4. 只有核心通过的 fresh nonce 才进入业务输入、role/account/exact grant、原 CID 和 acceptance 容量判断。有效 MAC 但 JSON/amount/path 无效、角色/grant/scope 拒绝、CID 内容冲突：nonce 消耗与一条带拒绝 outcome 的 audit 必须在同一 COMMIT；正常返回后才给出400/403/409。没有 accepted row。新 CID acceptance 配额满同样消耗 nonce 和审计后返回503 capacity，不删原记录。
5. 核心中的 key/time/replay/nonce 配额拒绝不插入新 nonce；能够实际提交 audit 后返回其 typed401/409/503。clock 不可用会回滚；clock regression 保留 durable highwater，能够提交其错误审计也不能签发成功 handle，响应为503 UNKNOWN。
6. audit 容量不足、append 失败、COMMIT 异常或回复丢失：整次事务的已知回滚或未知结果不能变成“403/409 已持久审计”的说法，统一503 UNKNOWN、无成功 handle。必须用当前授权的新 nonce 查原 AuthDB CID；不重发原 nonce，不换业务 CID。只有已正常返回的实际 COMMIT 才能声称 nonce/拒绝/接受已提交。

所有允许写入的请求在一个 AuthDB 事务内记录一条 request audit：`event=nonce_consumed` 表示核心成功；`outcome` 分别为 FIRST_ACCEPTED、QUERY_ORIGINAL、QUERY_MISS、INPUT_REJECTED、PERMISSION_REJECTED、CID_CONFLICT 或 RESERVATION_CAPACITY。核心拒绝使用其原错误 event。新的 first acceptance 外键指向这一真实 sequence，保存实际锁内 revision/grant epoch 和 request/nonce hashes。capture 时间或稍后 profile 读取都不能补造这些值。物理 COMMIT 时间不记录。

## First acceptance 永久语义与真正查询

业务键是 `(domain_id, tenant_namespace, account_id, business_CID)`；本期 tenant_namespace 明确等于 immutable auth_config.tenant。kind、payload hash、key/grant、epoch 和物理 authority 不入键。`auth_credit_acceptances` 的一行同时就是该键的 first acceptance 与 reservation，不另建可删除的临时去重表。首次 key identity/grant/epoch/audit/request bytes 永久不改、不删、不 replace。

新 CID 需要 funding + 当前 exact BTC credit.borrow 或 credit.repay。同 CID、同规范业务内容的 POST retry 还必须有当前 exact credit.read，只返回 query-only 记录，指向原 first_acceptance。另一有效 key/新 epoch 不能替换原 key 或 grant，原 key 重新授权也不能复活已撤销的原 grant。内容或 kind 改变是409。amount 的规范等价表示共用 business payload，但原始 body/request hash 保留第一次真实签名字节；retry 的新请求只留在自己的 query audit，不覆写原接受。

正常 first COMMIT 后发行的 auth_first_observation 也没有执行权。若 COMMIT 回复丢失，不构造成功对象；重启后的 lookup 使用实际认证、当前 credit.read 和新 nonce，返回 `auth_query_only`。独立的当前 reader/funding 可以查原接受，已撤销提交 key 不能仅凭旧 handle 发新查询。inspect 已交付本地 handle 只是阅读已存在的被动记录，不续期权限。H1 将来若要协调原 source 交付，需要独立受控 reader/protocol，不能靠 H0 重发 execution handle。

## Fresh schema 与旧格式拒绝

草案是七个 MAIN 表：`auth_config`、`auth_keys`、`auth_nonces`、`auth_audit`、`auth_credit_grants`、`auth_credit_grant_revocations`、`auth_credit_acceptances`。format2 config 添加 authority/domain/account 和精确容量，key 行保存与 identity 绑定的非秘密 role/account/not_before/expires，audit 保存实际 grant revision/outcome，grant/revocation/first acceptance 都有 append-only/全部 UNIQUE identity 的 no-replace 保护。

旧 format1 的 `_config` 在 configure/consume 的第一次 UPDATE/INSERT 之前检查 `_COLUMNS`/format。format2 改变原有 base 表列及 format，不能靠仅加三张表冒充安全版本；旧 reader 应先拒绝。新 loader 必须使用 MAIN-qualified catalogue/PRAGMA/table SELECT，核对完整 canonical CREATE、PK/FK/CHECK、xinfo/nullability/default/hidden columns、完整触发器与自动 index inventory，并做 main foreign_key_check。好 TEMP 不能隐藏坏 MAIN。missing/unknown/corrupt 格式不修复，不 CREATE IF NOT EXISTS。

必须实际做旧 format1 正控、新格式 reopen/旧 reader 拒绝和坏约束负控。还需使用自建临时 authority 验证：一个正常创建的旧 format1 对象在它原测试路径遭遇新的 format2 后，调用原 configure/consume 不能在拒绝前写入。原 format1 文件字节留存；这是未来明确授权的对抗性临时 fixture，不是迁移或覆盖现有库的功能。禁止用 __new__、虚构 Database/principal 或 mock verifier绕过真实构造来做正控。

## 容量、保留和并发

默认固定为 first acceptances256、grants64、active nonces2048、audit8192、本地 handles256。普通 nonce 上限1920，当前有效 credit.read 的 exact query/retry 可到2048；普通 audit 总数阈值7616，合资格 query 可到8128，可信离线 control 可到8192；普通 handle224，query 可到256。这是基于实际计数的准入阈值，保护查询和撤销不被普通请求耗尽；不是 OS 配额，也不保证在 query/control 自身把预算用完后仍可接纳。未授权 query 不能使用保留阈值。

这些实际 COUNT/row 判定与插入都在同一 BEGIN IMMEDIATE。已有 CID/lookup 不增加 acceptance 数；独立新 key 的每次业务尝试也不能覆盖 first identity。nonce 仅在 expires_ms < highwater 时允许 prune，等于保留。acceptance/reservation、grant/tombstone 和 audit 不随 nonce TTL 或容量压力删除，UNKNOWN 不会变成 ABSENT。永久记录/权限历史满时 fail closed；本期不提供自动 archive、重新初始化或容量提高。audit 满到不能证明持久拒绝时必须503 UNKNOWN，不伪称403已记录。

授予、撤销、profile/key 更新与接受共用 AuthDB 写事务。put_grant 生成实际锁内 epoch/revision，与 accepted receipt 引用值一致；原 grant 撤销永久，新的 grant 是新的身份。无关 key 的 profile revision 上升不自动撤销未变化 key。任何全局 revision/配额计数布尔冒充整数、负数、越界或 schema 漂移都拒绝。

Profile 更新只允许 profile-lock→AuthDB，或先取 immutable snapshot 释放 profile lock 后再进 DB 并验证实际 key identity。持 AuthDB 后禁止再取 profile 锁、重新 authenticate/consume 或构造会 configure 的 authenticator。issuer registry 仅短锁预留 slot，在进入认证/DB 前释放；实际 COMMIT 后填充预留 slot。H0 没有金融事务，也不证明未来跨库执行排序。

## 差异级工程拆分和待运行验收

拟在 root 指定909新分支只改 `uta/request_signing.py` 的共享私有核心，新增 `uta/credit_auth_h0.py`，新增对应认证测试。`RequestAuthenticator.authenticate` 的 signature/Credential 和旧 format1 结果保留。PR18 原 candidate-v1 与其 null/false 事实不动。gateway、writer_fence、credit_native_v2、credit_fifo_v2、风险/金融 audit、source/PENDING、listener/READY 的运行时改动全部不在 H0 范围。

独立组提出的12个 H0-I01..I12 已在机器契约逐项细化，**全部 NOT_RUN**：旧 API 正控/未启用无创建/exact schema与旧 reader/确定拒绝 nonce/真实COMMIT回复丢失后当前授权lookup/规范等价与冲突/撤销后不回绑/真实 grant竞争/strict nonce过期/配额与query/unknown及private identity/opaque PID Thread fork边界。原 HC-01..30 继续原样 NOT_RUN。本次纯检查不能算其中任何一项动态通过。

下一轮只有 root 审查此规范后才能批准代码和临时 DB 测试。建议每批30秒，CPU3/4由root指定；只用 fresh private synthetic AuthDB 和随机私有 keyfile，不开网络/金融DB。回复丢失须包住真实事务实际 COMMIT 返回，不伪造 receipt、authenticator、principal 或 gate。记录 exact SHA/command/cwd/runtime/SQLite/affinity、UTC和外层monotonic、原始stdout/stderr/exit/source hashes；失败/unknown 保留，不覆盖重跑。未获批准前不执行这些测试。

部署回滚：当前仅文档，无部署命令。未来 H0 fresh authority 中 accepted 记录和 tombstone 已存在后，不得通过删除/重建/降级 format1 来“回滚”。关闭入口、保留原认证库并前向修复；未交付金融 source 与 AuthDB 已接受是不同状态，H0 不知道金融结果。跨 epoch、备份防回退、存储丢失、HA/容量和真实资金仍未验收。
