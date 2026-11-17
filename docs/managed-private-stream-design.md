# Managed 私有事件 WebSocket：待审设计

状态：**DESIGN / NOT IMPLEMENTED / NO-GO**。固定代码基线
`a35fd56fc98126b3e5cced8a459bd04ca580e537`；本提交只增加设计、人工协议案例与静态证据。
没有新路由、listener、SQL、资金操作或上线许可，现有接口行为保持原样。本文的数值限制
和状态转移是本系统拟采用的政策，不冒称某个外部交易所的实现。

## 1. 最小切片与现状

第一切片仅提供一个账户的 `uta_events` 只读推送，以及连接开始时同一 RO 事务取得的
账户基础快照。快照包括原有 settled balances、分离的 principal/interest、订单/仓位数量；
**不包括完整订单/仓位快照、抵押可用额度、实时保证金或客户全量账本**。所有资金和
持久业务回执仍由原 fenced writer 产生。没有下单、撤单、还款、资金、账户模式切换或
客户端业务消息，也没有 global/operator firehose、跨账户订阅或跨片一致快照。

固定代码的事实与缺口：

| 现有代码 | 可保留的契约 | 新切片仍须实现 |
| --- | --- | --- |
| `durable_views.ManagedAccountViews.read` | 每次单一 SQLite RO snapshot；账户过滤先于 LIMIT；原 stream/cursor；不修复 schema | 同一连接内有更小容量前检的 stream-start/事件页读取；不可把多次 read 拼成原子快照 |
| `durable_views._context/_bounds/_page` | stream 绑定 authority/path/device/inode/account；全片 event watermark；正常序号 gap；end page 前进到 until | 数据源身份/游标变化后的 socket rebuild；bounded payload 读取 |
| `request_signing.RequestAuthenticator` | 签原始 target 和精确 body；nonce 在单独 auth WAL/FULL COMMIT 消费；持久轮换、撤销和时间 highwater | authenticate 目前只返回 Credential，没有长会话 key binding 或只读会话重检接口 |
| `gateway._Handler/_GatewayServer` | HTTP framing、TLS 边界、有限 HTTP worker 和脱敏错误 | `_reply` 固定 close；复用这些长期 worker 会挤占 REST；没有 RFC6455 frame/关闭状态机 |
| `durable_gateway._permit/_account` | REST reader/trader 账户范围，risk/admin 全局权限 | 首个客户 WS 只接 reader/trader，必须显式检查，不能继承 admin bypass |

`docs/durable-views.md` 和 `docs/managed-read-client.md` 是当前 REST 的依据。RFC6455
4、5、7 节是 transport 依据；原文 URL、读取时间及 SHA 见本提交静态证据。没有执行
协议或安全验收，也没有沿用以前的 PASS 作为本切片资格。

## 2. 独立 listener、握手及签名

拟新增 default-off 的独立 loopback `wss://127.0.0.1:8082` listener。必须显式提供已有
unbound producer、现有 deployment-bound authenticator 和 TLS1.2+ context；不能启动
writer、创建/修复 financial/auth DB、加载同步 v1 服务或自动暴露远程地址。与 REST
使用不同连接槽和进程资源预算；可共用同一已有 auth store，其 nonce 空间仍全局共享。
真实外部代理/边缘拓扑留待独立审查。本切片不接受 Bearer、cookie 或浏览器 Origin。
普通浏览器 WebSocket API 无法设置这些 HMAC 头；浏览器接入需要后续另审的会话协议。

端点：`GET /v2/accounts/{aid}/events/ws?challenge=<32小写hex>`。
首次连接不带 resume 字段；恢复必须同时带唯一 `stream_id` 和 `after`。不支持 `until`、
`at_version`、动态 subscribe 或其他 query；所有 query 的重复/未知/空值拒绝。原始 ASCII
target 必须与解析前请求行完全一致；不得规范化后验签。`after` 为 `0..2^63-1` 十进制整数，
`stream_id` 使用原 `account-stream:<64hex>` 格式。

握手必须是 HTTP/1.1 GET、无 body/Transfer-Encoding/Expect，Host、Connection、Upgrade、全部签名/WS singleton 头均唯一；沿用16KiB头界限。要求 `Upgrade: websocket`，Connection token 列表包含
Upgrade，唯一 `Sec-WebSocket-Version: 13`，唯一 base64 key 严格解码为16字节，唯一
`Sec-WebSocket-Protocol: uta.private.events.v1`。不协商 extensions；存在 extension offer、
未知 subprotocol 或多个协议时拒绝，不默默降级。challenge 必须等于该16字节 key 的
小写 hex，使现有 HMAC 的 raw target 同时绑定这个 transport key。它是公开握手随机数，
不是 auth nonce；两者每次连接都重新生成。签名继续使用现有 canonical-request v1，body
为真正空字节；不修改 REST 签名格式。固定 subprotocol 与 endpoint 绑定协议版本。

处理顺序：transport/framing/Origin/Cookie 与容量检查 → 原 HMAC authenticate/nonce
COMMIT → 显式 reader/trader 与账户范围 → source/cursor/快照预检 → 会话新鲜重检 → 101。
reader/trader 仅自己的绑定账户；funding/risk/admin 均403，运营流将另立权限与配额。账户
范围先于存在性查询，未授权连接不能知道该账户是否存在。已消费 nonce 不因后续403、
409或503回滚；重新握手使用新 key challenge、新 auth nonce 和签名，保留业务 stream/cursor。
连接满时在 auth/金融读取前429，签名尚未消费；客户端仍按上述新握手协议重试。

101包含 RFC accept、固定 subprotocol、Upgrade/Connection。`Sec-WebSocket-Accept` 使用
RFC示例的 SHA1+GUID算法；它不是账户鉴权。TLS/HMAC 未通过时不得发101或任何账户数据。

## 3. 会话权限、撤销和时钟

新增经审查的无 secret `AuthSessionBinding`：tenant、audience、producer binding、auth
store 的原文件身份、key_id、key.identity()、role/account、key有效区间和握手接受 revision。
不能把 secret、signature、原 nonce 或全 profile 带进队列/日志。现 `authenticate()` 返回
principal 不足以构造这个凭证；新握手入口须在同一次真实 nonce 消费之后返回精确 binding，
不能先 authenticate 再从另一次可变 profile lookup 猜 key 身份。

新增已有 auth DB 的 **mode=ro** 会话检查：原路径/文件/producer/tenant/audience/配置格式
正确，stored key 存在、未撤销且 identity 相等，当前受控 wall clock 在原有效区间内，且不
低于持久 highwater 或会话已见时间。身份变化/撤销/到期关闭1008；读失败、时钟不可用或
回退关闭1011；不缓存成功跨过数据发送。只读检查不消费新 nonce、不建立新 auth schema，
也不假装只读时更新了 durable highwater。控制面仍通过原 configure/replace_profile 审计。

mode=ro表示SQL只读，不是“目录零写入”证明：cold WAL可能需要auxiliary WAL/SHM；
若严格RO挂载下sidecar缺失导致读取失败，关闭/返回unavailable，不创建financial schema、
删除sidecar、复制混合live文件或改用live immutable=1。文件身份前检沿用stat，不对已发布
SQLite主inode做原始open/fstat/close，以免触发同进程POSIX锁释放问题。

每次取得数据后、每个 application frame 开始发送前都重新检查；空闲时目标每250ms检查，
成功检查到首字节的授权 age 上限100ms，超过即重新检查。profile revision 增加而同一 key
identity 仍有效可继续；删除/撤销的旧 key 不能因内存旧 profile 继续。每连接最长15分钟，
到期用1008与 `session_expired` 结束并要求新握手，不做 frame 内续期。

本地观察到撤销后不再开始任何账户数据 frame。检查后撤销与发送之间存在竞态，已开始
发送/已进入内核的 bytes 不可撤回；两个 DB 之间没有原子撤销/金融快照事务。正常可响应
调度/存储下的关闭目标为1秒，**尚未测量，不是任意 I/O 故障的硬 RTO**。发送每帧最多
500ms；重检、读或发送逾期不使用旧授权继续。故障时即使关闭被OS阻塞，也不得补发数据。

## 4. 基础快照、增量与恢复

未带 resume 的连接：在一个新的短 RO 事务内，以原 authority/shard identity 核验为基础，
读取账户基础投影、原 metadata、stream_id 和全片 event watermark **H**。关闭事务后
发送 `snapshot`，声明 `coverage: account_base_only`、`cursor_after: H` 和不支持字段；随后
只读 `sequence > H`。快照取得后、101前的新成交仍保存在事件日志，按 after=H catch-up，
不得只从“当前时间”开始而漏掉这段。没有长期保持 SQLite snapshot 或为网络写持有读事务。

resume 连接：要求匹配 stream_id、after≤当前 watermark，在同一 RO 事务取得第一个
固定范围 `(after,H]`。发送 `resumed` metadata，**不发送一个今天的账户投影覆盖客户端
旧基线后再重放过去事件**。每个事件页另有自己的 observed_snapshot；多页可处于不同
账户版本或market/config，不说成一个大账户原子快照。每个范围固定 until=H；按原页
`next_after` 前进，排完再开启新范围。不对 tail 施加 at_version，避免正常更新永远409。

事件使用原 `(stream_id, sequence)` 去重。sequence 是分片全局序号，另一个账户或全局
控制事件造成的407→413正常，不填充、连续性报警或泄露其记录。空 private 页也可把
next_after 前进至 until；必须发完整 empty-page checkpoint 才能让客户端持久该前进。
heartbeat/ping 本身不推进已应用 cursor。独立的 connection-local frame_id 只用于诊断，
重连从1开始，不能代替任何持久 event/ledger cursor。wire沿用有界JSON整数，客户端必须
无损解析至64bit/arbitrary precision；`9007199254740993`不能经binary float变成
`9007199254740992`。首片不提供浏览器SDK，后续SDK必须单独验证此边界。

客户端只在自己的事务里原子“应用整个页/更新 durable cursor”后记录 next_after；收到
bytes、pong、TCP ACK或server last_sent 都不是已应用证明。响应丢失后重复页正常；同一
stream/sequence 如出现不同内容是数据一致性错误，停止并对账，不以最后收到者覆盖。
服务端首片没有持久 subscriber ACK、server cursor 或 exactly-once delivery 承诺。
初始snapshot同样只有在客户端原子保存基础投影与H后才成为可恢复基线；收到snapshot后
未保存就崩溃，应重新snapshot，不能仅拿网络看到的H当作本地已应用游标。

事件流是已存业务通知和刷新依据，不是已验证的全账户 reducer。未知 event_type 必须保留
原事件并按客户端策略重建 REST；不能忽略后继续声称余额已复算。订单/仓位行游标与 ledger
sequence 是其他域；不得代入本 after。客户完整订单/仓位重建仍沿用 REST at_version
协议；REST多个响应也不会因此成为一个时点快照。行情 stale/future/missing、risk unsupported、
null reserves、not_evaluated 原样传递，不转成 ready、可用资金或交易授权。

stream/file/authority变更或 ahead cursor：101前409；已连接时发可容纳的 error再关闭4000，
不自动归零、换stream或从新水位续发。当前没有历史删除/retention迁移协议；本片只支持
历史保留的authority，不发明 `min_retained`。任何实际检测到的非法截断/冲突均失败关闭。
现有stream的inode语义不防可信OS owner原位回退或整机克隆；须保留此证据缺口。

## 5. 有界读取、背压与 frame

不能直接取 REST limit200×每payload4MiB，再在序列化后截断。须实现独立有界 RO helper，
在**同一连接/事务**先取得有序候选的 sequence/原payload UTF-8字节长度，再读/解析受限行。
首个合资格事件超过64KiB时不跳过、不前移cursor，关闭1009与 `event_too_large`。页最多32
事件、原payload合计128KiB、最终编码 frame最多256KiB；合法prefix可在下页继续，不能把
截掉的事件计入 next_after。非payload metadata与字符串也须typed/长度校验，JSON严格
拒绝 duplicate keys/NaN/Inf/溢出、深度>32、单容器items>512或损坏值；不能让宽容fallback发送错误财务事实。

stream-start 基础投影最多256个assets、256个liabilities且最终frame≤256KiB。容量前检与
实际数据必须在同一RO事务，不能前一次COUNT之后调用另一次read冒称一致；超限返回
503 `stream_snapshot_capacity_exceeded`，没有部分快照。现REST的4096上限不因此改变。
需要重构共享同连接的投影读取，保留既有REST响应/权限/保护行为；实现与差分测试尚未做。

出站最多2个已编码frame、总512KiB，另一个正在读取/编码的frame≤256KiB。缓冲满就停止
新金融读取，不从日志丢中间事件或以最新快照覆盖未送页。5秒未排空或最老待发页年龄>5秒
关闭4008 `slow_consumer`；客户端从最后本地持久cursor恢复。队列满不会阻塞writer、消耗
cancel/repay容量、改变预占或清算状态。无连接时没有持续全市场轮询/fanout。

| 资源 | 首片拟定默认/上界 | 验收要求 |
| --- | --- | --- |
| 总连接/每key/每account | 8 / 2 / 2；配额只在本listener进程内 | 跨进程全局限流尚未提供，禁止乘副本冒称全局约束 |
| 握手/入站control速率 | 本进程8次握手/秒burst8；每key1次/秒burst2；每连接control32次/秒burst64 | 全局桶在auth前，key桶在真实验签后；超限429或已连接1008，不消耗资金队列 |
| 握手/入站header | 3秒 / 16KiB | 防慢握手、重复头、无资金读取拒绝 |
| 轮询 | 每活跃连接不高于4次/秒；一次只一页RO | 无reader backlog无界积累；公平round-robin |
| RO查询 | reader timeout50ms，VM progress deadline50ms | 仅reader设置，不改writer busy timeout；OS I/O不构成硬deadline |
| frame/queue | 256KiB / 2frames且512KiB | 高水位停止读，低水位再读；编码前与后均计量 |
| 心跳 | idle15秒ping，匹配pong期限10秒 | monotonic实际时间；缺pong正常关闭1001 |
| 连接寿命/发送/排空 | 15分钟 / 每frame500ms / shutdown2秒目标 | 关闭超时释放自有socket；不过早推进cursor |
| 进程 | 单独部署，拟256MiB RSS容器硬限 | JSON/SQLite/线程 heap开销须实测，wire字节上限不证明RSS上限 |

仅发送未压缩、未分片、FIN=1的text application frame。所有客户端frame必须masked；
RSV=0；长度字段最短编码，64bit长度高位为0；控制frame≤125且FIN=1。输入data frame无论binary/text均不支持，分别1003/1008；有效
fragmented text同样属于本应用不接受的data，不谎称它违反RFC。没有未决message的
continuation、非法opcode/RSV或fragmented control才是1002。本片是明确限制客户端消息
的应用profile，不宣称交付可接收任意RFC6455数据message的通用endpoint。
控制payload最多125字节，解析header后立即拒绝超限，不能按声称长度先分配内存。server
frame不mask。客户端close理由须合法UTF-8、合法wire close code，不能发送1005/1006/1015；
格式错误1002、非法UTF-8 1007。ping原payload pong；
只有匹配pong才清除未决ping；RFC允许的unsolicited或不匹配pong忽略/计数，不当财务ACK
或推迟原pong deadline。server close后不再发application数据，等待peer close或2秒后关闭。

## 6. 错误与版本契约

101前沿用脱敏JSON错误；401 HMAC、403角色/账户/Origin/Cookie、404授权内不存在账户、
409原view_stream_changed/view_cursor_ahead、429 stream_capacity_exceeded、503 auth/view
不可用。版本不为13使用426及 `Sec-WebSocket-Version: 13`；其他握手错误400。错误不
回显原signature、nonce、headers、SQL、完整路径或其他账户存在性。101后不能再发HTTP
JSON response；最多一条有界 `{wire_version:1,type:error,error:{code,retry,rebuild}}`再close。

| close | 场景 | 客户端动作 |
| --- | --- | --- |
| 1000/1001 | 正常关闭/服务drain/心跳超时 | 从本地已应用cursor重连 |
| 1002/1003/1007/1008 | frame协议/不支持binary/UTF-8/策略或权限到期撤销 | 修正协议或权限；不得自动换Bearer |
| 1009 | frame或单事件容量超限 | 不前进cursor；查询REST/联系运营，不循环跳过 |
| 1011 | auth/view/storage/clock未知或完整性错误 | 原cursor保留，退避调查；不重建财务状态来“修复” |
| 4000 | stream_changed/cursor_ahead/检测到非法历史变化 | 丢弃不兼容旧基线并按REST重建；不静默重置 |
| 4008 | slow_consumer | 降低客户端处理延迟，按原stream及durable cursor恢复 |

`uta.private.events.v1` 与每个JSON `wire_version:1`一起固定契约。新增不影响语义的optional
字段可向后兼容；改变cursor域、快照覆盖、权限、mask/fragment或事件载荷语义须新subprotocol。
旧client明确拒绝未知version。不能通过重命名版本假装现有生产者已提供更多事件覆盖。

## 7. 人工案例、实施顺序与验收

[人工协议fixture](../tests/fixtures/managed_private_stream_v1_contract.json)含真实RFC accept
字节向量、仅合成HMAC例、snapshot→有gap事件→空页前进→重复页恢复、changed stream、
撤销、mask/fragment/slow consumer及大事件拒绝。expected是**未实现的要求**，不称测试PASS。
JSON/摘要/签名算术静态检查只证明文档自洽，不执行网络或证明权限/交付。

拟分独立提交，并由另一工作组复核：

1. 批准本设计及拒绝矩阵，独立构造逐字节frame/HMAC/nonce/跨账户/撤销反例。
2. 纯frame codec/有界buffer及无secret会话检查；不接金融路由，真实socketpair/自有auth
   临时库测试，涵盖部分read/write、close交错、重复nonce和进程重开。具体GO另行授予。
3. 同RO snapshot的bounded start/page helper及独立SQL oracle；并发写入时检验H边界、
   正常gap、oversize未跳过、source换inode、丢失page后重放。没有修改金融表或启动writer。
4. default-off独立TLS/HMAC listener接线；真实连接/key撤销/背压/公平/资源释放与REST
   隔离测试。读权限需在financial查询前验证，任何route不能调用financial命令。
5. 固定源码三本地运行时/八CI/真实wheel+sdist/安装后TLS与恢复/故障注入/独立审查；
   新load计划单独批准，测量query/网络/RSS/时延及writer干扰，不能借订单吞吐替代WS容量。

独立验收可否决启用：按页正确性、授权撤销race和失败语义、资金表/nonce边界、真实
descriptor/RO行为、bounded坏帧与slow reader、进程重启后重复去除、无线程/FD泄漏均须实际
证据。未来接入PM、现货、借款或全账户reducer时重审事件覆盖，不能自动继承首片资格。

## 8. 规则追溯（尚未生效）

| 拟定规则 | 来源/版本 | 单位与边界 | 人工案例 | 验证缺口 |
| --- | --- | --- | --- | --- |
| LOCAL-WS-AUTH-001 | 本地policy-v1；现canonical HMAC-v1；RFC6455§4 | 时间ms、空body SHA256、固定role/account；持久nonce消费与金融DB非原子 | C001、C008–C013、C029 | 会话检查、真实撤销race/轮换/时钟故障待实现与独立审查 |
| LOCAL-WS-CURSOR-001 | 原managed views-v1；拟定events-v1 | 全片整数sequence 0..2^63−1；同stream正常gap、客户端原子apply | C002–C007、C027–C030 | 无跨片/全reducer/外部anti-rollback证明；多页非单快照 |
| LOCAL-WS-FRAME-001 | RFC6455§4/5/7；本应用restricted profile | bytes、合法control≤125；不接受客户端业务data；合法fragment与非法frame分开 | C014–C023 | 编解码/部分IO/关闭状态机尚未实现，未宣称通用RFC endpoint验收 |
| LOCAL-WS-BOUND-001 | 本地容量policy-v1 | 原event≤65536bytes、page≤131072、frame≤262144、queue≤524288；不跳过超限事件 | C024–C026 | RSS/读写deadline/慢消费者与writer干扰均待实测 |

产品仅现有合成账户通知，模式不新增；货币金额沿用原字符串/asset_units，不生成汇率或保证金。
所有规则effective time为 **NOT_ACTIVE**，接口版本为proposed `uta.private.events.v1`。父级
生产规则矩阵不能把这些拟定条目视为已启用；外部交易所API/行为映射不在本证据范围。

## 9. 部署、回滚与明确未交付项

实现后只在新的合成环境配置已存在的private producer/auth authority、固定artifact、TLS及
独立进程配额，listener默认disabled；先RO核身份和预算，独立审查后显式启用。无需financial
schema迁移，不改变模式、订单预占、nonce格式、借贷政策或清算。监控连接数/配额拒绝、
auth检查年龄、最老待发页、queue字节、poll/read年龄/超时、close code、重建、重复冲突与
REST/writer影响；不记录完整客户event/header/signature或虚构“客户已应用”指标。

回滚：停止新握手，发1001 drain并停止新读取，结束自有socket/reader任务后停止新进程；
保留客户原stream/cursor，REST读接口继续使用原契约。若已消费nonce，仍保持原auth表和
highwater；不删nonce、不回退profile revision、不恢复financial旧备份。回滚不用释放订单
资金、修改账务或重置writer generation。结果未知只影响投递，不能作为财务重放命令。

本轮未实现/验收listener、frame、会话重检、bounded reader、全局限流、订阅ACK、完整账户
事件reducer、私有WS生产容量、复制/跨AZ恢复、真实资金或金融审批。所有live job与固定
M2 source保持独立；本设计不能改变它们既成NO_GO或提供未来时长通过证明。
