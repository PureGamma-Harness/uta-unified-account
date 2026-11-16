# Durable v2 HMAC authentication

`uta.request_signing` 为 durable `/v2` 入口增加显式 HMAC-SHA256 profile 与持久 nonce 重放防护。原 `/v1` 没有变化，v2 原 Bearer 入口仍可用于 loopback 开发。**生产接入门槛要求显式 `auth_profile="hmac"` 与 TLS；本功能及合成测试通过不代表 G7、容量或金融规则签批已经通过。**

签名模式不会回退 Bearer。缺失/错误 HMAC、失效 key、nonce 重放、认证数据库故障都不会调用命令 enqueue。HMAC profile 的 401 challenge 也是 `UTA-HMAC-SHA256`，不会提示客户端改用 Bearer。公开 `/healthz` 只报告进程存活，不包含金融数据。

## 身份与初始化

一个 HMAC 入口绑定一个 tenant 和一个实际金融 producer。首次显式离线初始化认证库时生成随机 UUID audience，持久保存，重启不重新生成。不同部署即使产品/风控/layout 相同也获得不同 audience。

```python
from uta.durable_gateway import producer_binding
from uta.request_signing import NonceStore

# producer 是已经存在的 QueueStore(initialize=False) 或 DurableProcessRouter。
# 此初始化只执行一次，不得在每次服务启动时重建认证库。
store = NonceStore.initialize(
    "/var/lib/uta/request-auth.sqlite3",
    tenant_id="tenant-a",
    producer_binding=producer_binding(producer),
    past_window_ms=30000,
    future_skew_ms=5000,
    max_nonces=100000,
)
audience = store.audience  # 非 secret 的部署身份，填入该部署签名配置。
```

绑定摘要含实际 authority ID、canonical 数据库路径及本机文件 device/inode；router 包含实际 control/shard 文件，不能用 policy/layout hash 代替部署身份。factory 核对该摘要与当前 producer 一致。认证库和金融库是不同的数据库，认证库构造器只打开已有文件，不会在文件消失时自动重建。

同一 tenant 的多 HTTP 进程共享**同一个本机认证库**，因此 nonce 唯一性与撤销状态跨进程生效。没有实现跨主机 nonce 复制、跨地域共识或全局克隆检测。认证库移动到其他路径会被拒绝；对被信任 OS 用户原地还原旧认证库快照、复制整台机器/文件系统、同时恢复旧金融库等情况，这个本机绑定不是外部反回滚证明。不能据此声称备份恢复后仍有全局防重放保证。

## 私有 keyfile

`load_profile(path)` 只读取 service-user-owned 普通文件，禁止符号链接与组/其他用户权限；推荐 `0600`。最大 64 KiB，严格字段、重复 JSON key、重复 key ID、非规范 base64url、错误角色/账户与日期均拒绝。

配置格式如下，所有占位值必须由离线管理流程替换，不能直接部署：

```json
{
  "format": 1,
  "tenant_id": "tenant-a",
  "audience": "uta:<persistent-generated-uuid>",
  "revision": 1,
  "keys": [
    {
      "key_id": "alice-v1",
      "secret_b64": "<unpadded-base64url-of-32-or-more-random-bytes>",
      "role": "trader",
      "account_id": "alice",
      "not_before_ms": 0,
      "expires_at_ms": 0,
      "revoked": false
    }
  ]
}
```

实际 secret 必须来自密码学随机源，解码长度 32..128 bytes，不能使用测试 secret 或人为密码。`not_before_ms`、`expires_at_ms` 是明确的 epoch-millisecond 整数，后者必须大于前者；示例中的零值不是有效运行期限。请求时间与当前服务器时间均须在 key 的有效期内。

角色与账户验证复用既有 `Credential` 规则：reader/trader/funding 必须绑定账户，risk/admin 不绑定单个账户。所有这些 key 都属于该入口的同一 tenant；单 tenant 内的 risk/admin 仍按既有 v2 权限工作，不能把一个全局 admin key 解释为跨 tenant 的授权。需要多个 tenant 时，为每个 tenant 使用独立的 producer 绑定、认证 authority/audience 与配置。

## 生产 profile 与 TLS

正常启动只打开已有认证库、加载私有配置，再构造 signer：

```python
import ssl
from uta.durable_gateway import make_server
from uta.request_signing import NonceStore, RequestAuthenticator, load_profile

authenticator = RequestAuthenticator(
    NonceStore("/var/lib/uta/request-auth.sqlite3"),
    load_profile("/etc/uta/signing-keys.json"),
)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.minimum_version = ssl.TLSVersion.TLSv1_2
context.load_cert_chain("/etc/uta/server-chain.pem", "/etc/uta/server-key.pem")
server = make_server(producer, auth_profile="hmac",
                     authenticator=authenticator, tls_context=context)
```

HMAC profile 默认 `require_tls=True`，没有 TLS context 会在构造阶段拒绝，不接收额外 Bearer credentials。监听仍只允许 IPv4 loopback；远程入口需要明确的 TLS/代理部署与证书验证。TLS 握手在已受并发 cap 与 socket deadline 限制的 worker 中进行，静默 TCP 连接不会占住整个 accept 线程。

`require_tls=False` 是显式的合成 HTTP/本机开发例外：仍验证 HMAC，但**不满足生产的 HMAC+TLS 门槛**。它不能作为绕过证书、验证 TLS 终止代理或生产签批的布尔开关。客户端生产代码必须验证服务端证书；测试里的未验证自签名 TLS context 仅供合成回归。

factory 不自动安装信号处理、启动金融 writer 或提供新 CLI flags。调用方继续管理 HTTP drain、producer 和 writer 生命周期。HMAC 认证本身不初始化金融 service 或放宽 fencing。

## 精确签名协议

每个受保护请求需要以下单份 header；重复字段会拒绝：

| Header | 格式 |
| --- | --- |
| `Authorization` | `UTA-HMAC-SHA256`，没有 Bearer token |
| `X-UTA-Version` | 字面值 `1` |
| `X-UTA-Tenant` | 配置中的 tenant ID |
| `X-UTA-Audience` | 持久 audience |
| `X-UTA-Key-Id` | 该 profile 中的 key ID |
| `X-UTA-Timestamp-Ms` | 无前导零的 epoch-ms 十进制字符串 |
| `X-UTA-Nonce` | 22..128 个 base64url 字符，建议 `secrets.token_urlsafe(24)` 或更强随机值，每次请求新建 |
| `X-UTA-Signature` | HMAC-SHA256 的 64 位小写十六进制值 |

canonical bytes 是下面数组的 **compact JSON、ASCII 编码**，分隔符严格为 `,` 和 `:`，没有结尾换行：

```text
["UTA-HMAC-SHA256","1",tenant_id,audience,key_id,timestamp_ms_as_string,nonce,method,raw_request_target,sha256_exact_body_as_lower_hex]
```

计算 `HMAC-SHA256(secret_bytes, canonical_bytes)`，使用 constant-time digest comparison 验证。method 为原大写 HTTP method；request target 是原始 ASCII origin-form，包含未重排的 query，最大 2048 字符。不能先做 URL 解码、query 排序、JSON 重新格式化或金额规范化再签名。body 摘要覆盖实际发送的每个 byte，包括空格与换行；GET 无正文时哈希的是空 byte string。现有 v2 路由仍可拒绝不支持的 query/路径。

服务核对原 request line 与路由 target 一致，拒绝基础 HTTP parser 的模糊归一化。正文仍有现有 64 KiB、Content-Length、UTF-8 与严格 JSON 限制；签名不会替代这些校验。

客户端可使用本模块的确定性 helper：

```python
import json, secrets, time
from uta.request_signing import sign_headers

target = "/v2/accounts/alice/orders"
body = json.dumps({"command_id": "stable-command-1", "order_id": "o1",
                   "symbol": "BTC-PERP", "quantity": "1", "limit_price": "100"},
                  separators=(",", ":")).encode("utf-8")
headers = sign_headers(profile, "alice-v1", timestamp_ms=time.time_ns() // 1_000_000,
                       nonce=secrets.token_urlsafe(24), method="POST",
                       request_target=target, body=body)
# 通过验证证书的 TLS client 发送同一个 target、body bytes 和这些 headers。
```

## Nonce commit、清理与 wall clock

默认允许过去 30 秒、未来偏差 5 秒；初始化 bounds 分别为过去 1..300000 ms、未来 0..30000 ms。窗口属于认证库不可变策略，不能在清理后扩大窗口重新接受旧请求。

验证 HMAC 后，服务获取认证库 `BEGIN IMMEDIATE`，**在取得事务锁之后**采样服务器时钟，避免两个正常并发请求的锁前采样倒序被误判为回退。nonce 的 `(key_id, nonce_hash)` 在绑定 tenant/audience 的认证库中唯一，成功 INSERT 与审计记录通过 WAL/FULL COMMIT 后，才执行 v2 role/route/业务 enqueue。

认证库持久保存 server wallclock highwater。时钟低于 highwater 时返回 503 `auth_clock_regressed`，不会降低 highwater、清 nonce 或回退内存存储。nonce 保留到 `request_timestamp + past_window`；只有 `expires_ms < highwater` 才允许删除，等于边界时仍保留。未来偏差内发送的请求也获得完整窗口。nonce 清理后回调时钟不能把旧签名重新变成合法请求，重启也不重置这个高水位。

超过 `max_nonces`（默认 100000、允许 1..1000000）时返回 503，不能驱逐仍在可重放窗中的 nonce 来腾位置。空闲期可暂存已过期条目，后续有效签名事务安全清理。nonce/audit 写入量、磁盘容量、轮询倍率、数据库锁时延和时钟运维都需要单独容量验收，本次没有提供生产 TPS 保证。

认证库缺失、锁失败、损坏、schema/完整性 guard 缺失均返回 503，无内存 fallback、自动重建或 Bearer 降级。异常后 nonce 是否已提交可能未知；这不授权服务器猜测业务结果。

## 轮换、撤销与恢复

`SigningProfile.revision` 持久单调增加，同一 revision 只能是同一规范内容。key ID 永久绑定 secret fingerprint、role/account 与有效期；改变这些属性必须使用新 ID，不能复用已撤销 ID。

轮换流程：revision N+1 同时保留旧 key 和新 key，调用 `authenticator.replace_profile(load_profile(path))`，并让全部 HTTP 进程加载新 profile；客户端改用新 key 后，用下一 revision 移除旧 key 或标记 `revoked=true`。移除会在共享认证库永久撤销旧 ID。仍持有旧内存 profile 的其他进程也会在每次 nonce 消费时读取这个撤销事实，不能继续使用旧 key。滞后进程在加载新 key 前可能拒绝新 key；不得用 Bearer 来补偿。

配置文件变更不会自动热加载，HTTP 没有修改签名 key 的接口。过期 key 在服务器当前时间或请求时间越界时拒绝，不能通过改 timestamp 延长 key 生命周期。

通信失败、丢响应、403/400 等业务/权限失败之后，客户端下一次请求都使用 **新 nonce**。若原 durable command 结果不确定，保持 **原 account、command ID 和业务内容**，用新 nonce 查询或重试；nonce 不是 command ID。

认证 nonce 被消费只证明一次 HMAC/新鲜度/唯一性认证，可能随后因 role/scope/JSON/queue 容量而拒绝，甚至未能 enqueue。`202 durably_queued` 又只证明命令入队；后续 `SUCCEEDED/REJECTED/QUARANTINED` 仍按 [durable API](durable-api.md) 的 worker 回执处理。两个 COMMIT 是刻意分开的，不会把认证成功伪造成金融接受。

不要通过删认证库、降低时钟高水位、重新生成相同 audience、回滚旧 key/nonce 快照来“恢复服务”。原地旧备份恢复与全机 clone 没有外部全局反回滚证明，必须有停机、撤销/新 audience、新 key 及金融对账的受审恢复协议；这里没有自动化实现这个协议。

## 审计与错误

认证库保存 profile revision、不可逆 key identity fingerprint、nonce hash、canonical request hash、request/server timestamp 与事件类型。审计追加且不自动删除；不保存 secret、HMAC signature、原始 nonce、正文、URL 或数据库路径到审计行。已通过密码学验证的重放、失效 key 和时钟异常可以留下脱敏拒绝审计；无效 MAC 不额外制造数据库审计写入。

`nonce_consumed` 是认证事实，不是 role 授权、入队或金融结算审计。长期审计归档、容量与访问控制需要运维规划，不能用删除 live nonce 或回滚认证库代替归档。

| HTTP / code | 含义 |
| --- | --- |
| 401 `signature_required` / `invalid_signature` | 签名字段缺失、格式错误、域/方法/target/body/MAC 不匹配，无 Bearer 回退 |
| 401 `signing_key_inactive` | 已撤销、未生效或过期 key |
| 401 `request_timestamp_out_of_window` | 超出过去/未来请求窗口 |
| 409 `request_replayed` | 该 key 的 nonce 已消费，下一请求换新 nonce |
| 503 `signing_store_unavailable` | 不能从持久认证 authority 获得可信结果，不 enqueue |
| 503 `auth_clock_regressed` / `auth_clock_unavailable` | 服务器认证时钟不可用或低于持久高水位，fail closed |
| 503 `signing_capacity_exhausted` | live nonce 容量已满，不安全驱逐被拒绝 |

其他 HTTP/framing、账户角色、durable queue 错误保持原语义。客户端按 code 处理，不能把错误 message 当稳定协议。

## 合成验证

`tests/test_request_signing.py` 覆盖独立 canonical/MAC 向量、全部签名域、精确窗口边界/未来 skew、清理后 wallclock 回退与重启、唯一新部署 audience、复制认证库拒绝、过期/永久撤销/多进程旧 profile、私有配置与脱敏审计、authDB 丢失/损坏 fail closed、两个真实 HTTP PID 同 nonce 竞争、真实丢 HTTP 响应后的新 nonce+原 command ID 恢复、权限隔离，以及真实合成 TLS 和静默 TCP 不阻塞监听。现有 durable Bearer 开发回归继续运行。没有使用真实 key 或客户资金，也没有通过 G7 生产批准。
