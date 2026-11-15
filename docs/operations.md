# 部署、备份与恢复

## 可选精确计算缓存

0.3.0a1 的 `exchange` 命令新增 `--reserve-cache-size 0..65536` 与 `--market-cache-size 0..64`，默认均为 0。显式设置例如 `4096 / 4` 才启用；容量非法会在创建金融数据库前拒绝。缓存只减少纯预占数学与行情解码，不保存余额、可用额度、行情新鲜度或准入决定，不改变产品和资金权限。

每个 service 实例独立占用容量，多个 shard/进程会相乘；数量上界不是硬 RSS 上界。risk/admin 可在 `/metrics` 查看 `risk_cache.reserve` / `risk_cache.market` 的命中、容量、淘汰及解码异常计数，客户角色不可读全局诊断；这些计数不随事务回滚，不能充当成交或预占账本。

暂停新增风险并排空全部写者后，同一完整数据库用容量0/0重启即可回到原参考路径。缓存清空不撤销已确认业务；未知结果仍用原 ID 恢复。分片 adapter 只能回退到原 router 接口，不能绕过 control/身份/资金凭证屏障。完整证据、分片接入和版本降级步骤见 [本轮报告](milestone-kernel.md)、[分片准入契约](shard-admission.md)。当前仍不是生产启用批准。

## 可选分组接纳运行模式

该模式默认关闭。需要评估时，在原 `exchange` 命令上显式增加：

```sh
--batch-admission --admission-batch-size 32 --admission-delay-ms 2 \
--admission-queue-capacity 1024 --admission-cancel-reserve 16 --admission-timeout 2
```

batch size 为 `1..256`，最大组装延迟为有限的 `0..1000ms`，普通待执行容量为 `1..65536` 条，另有 `0..4096` 个撤单保留槽，HTTP 结果等待为 `.001..60` 秒。总待执行容量严格有界；撤单保留容量不改变 FIFO 顺序。无效参数在打开资金数据库之前拒绝。默认同步路径不变，生产启用状态和容量门槛也不因开启此参数而改变。

HTTP 先绑定成功才创建非 daemon 分组 worker。正常 SIGTERM 停止接收新连接，停止风险调度、排空已接收的 HTTP 处理器，再关闭并排空已接纳的分组队列。等待超时不会回滚已经开始的交易；遇 `command_result_unknown`，按原命令 ID 查询或重试，不得重命名命令。进程被强杀时，重启后依据实际持久订单和幂等记录恢复，而不是依据客户端超时猜测执行结果。

监控 `admission.queued/running/overloaded/technical_failed`、commit 批次数及命令数，并保留排队到 COMMIT 的端到端延迟。队列满应在上游退避；不要通过无限扩大队列隐藏过载。停止或失败的批处理组件使 readiness 失败，但不修改原资金账本。升级/回退前按既有恢复手册停止所有写者、完整备份并核对已经确认和结果未知的命令。

本运行手册适用于单节点合成 UTA 的本机集成与预发布验收。服务使用本地 SQLite 保存账本、账户、现货/线性订单和借款；正式配置路径使用同一版本的产品目录及 Cross 保证金规则，缺省路径保留原线性参考模型。测试通过不构成真实交易所上线认证。

## 安装与运行

需要 Python 3.10 或以上版本。运行时只依赖 Python 标准库。SQLite 文件必须放在受访问控制的本地持久磁盘，不能放在 NFS、共享网络卷或容器临时文件系统上。部署一个活跃服务进程；数据库跨连接竞争测试不代表主从切换、分布式事务或高可用已经实现。

从审查过的 commit 构建 wheel，并保留 commit SHA 和 wheel 的 SHA-256。以下命令在仓库目录执行：

```sh
python -m pip wheel . --no-deps --wheel-dir dist
python -m venv /opt/uta/venv
/opt/uta/venv/bin/python -m pip install --no-deps dist/*.whl
```

由系统管理员创建专用 `uta` 用户以及 `/var/lib/uta` 和 `/etc/uta`。数据库目录归服务用户所有且权限为 `0700`，其他用户不得读取客户数据。数据库自身也必须为服务用户所有的私有常规文件，拒绝组/其他权限及最终路径符号链接。先在合成账户上验收，服务不会创建真实资金、接入外部撮合或自动拉取价格。

`/etc/uta/credentials.json` 是 JSON 数组。凭据文件必须归服务用户所有、权限 `0600`，且不是符号链接。每个 token 用 `python -c 'import secrets; print(secrets.token_urlsafe(32))'` 单独生成，不复用下面的占位文本：

```json
[
  {"token": "REPLACE_WITH_INDEPENDENT_ADMIN_SECRET", "role": "admin"},
  {"token": "REPLACE_WITH_INDEPENDENT_TRADER_SECRET", "role": "trader", "account_id": "alice"}
]
```

reader/trader/funding/risk/admin 权限见 API 契约。配置目录的服务只能通过真实双侧撮合 REST 结算；旧参考模式的管理员手动 fill 是本地执行授权边界，不接收不可撤回的外部已成交事实。当前撤单只改变本地权威订单，不会发送外部撤单确认。接入真实外部撮合前，必须实现专用的成交对账、未知结果和撤单确认适配器。

交易员及资金凭据绑定账户，权限分别发放。凭据不放入命令行、版本库、HTTP 日志或工单；泄露后换凭据并重启服务，嵌入式调用可用 `server.replace_credentials()` 原子轮换。没有公开在线轮换端点、MFA 或完整 IAM。

```sh
/opt/uta/venv/bin/python -m uta exchange \
  --database /var/lib/uta/exchange.sqlite3 \
  --credentials /etc/uta/credentials.json \
  --asset-scale USD=8 --asset-scale BTC=8 \
  --catalog /etc/uta/products.json --risk-rules /etc/uta/risk-rules.json --automate \
  --host 127.0.0.1 --port 8080
```

将审查过的产品及规则配置放入上述两个路径；隔离演示可以从 `config/` 复制合成模板，不能将其用于真实资金。两份配置必须成对提供并与数据库保存版本一致，省略参数不能降级已配置的库。默认无参数仍为 `USD=8` 参考模型；重复 `--asset-scale` 时应列出全部资产。重新打开时资产精度必须完全一致。HTTP 只监听回环，远端需 TLS 反代及请求/连接/速率限制，标准库服务没有公网网关容量保证。

`--automate` 运行账户风险监督和真实本地对手撮合；没有流动性时保留残余风险，不生成标记价成交。已知账户业务错误按账户记录并继续调度。未知 worker 异常请求持久全局暂停并使 readiness 失败；运营应调查 `worker_failure`，重放对账后显式解锁，不自动清空暂停。无合约持仓的借款风险目前冻结并标 `loan_liquidation_adapter_required`，尚无自动抵押转换/强制还款适配器，不能视为借贷生产清算通过。

运行 `python -m uta acceptance` 可在临时数据库中执行合成资金的交易验收场景，不需要网络、真实凭据或外部执行器。部署前应在所安装版本上保存其输出。启动服务还会执行账本完整性验证；这能检查内部 journal 与余额的一致性，不能替代外部资金与成交对账。

`GET /healthz` 只反映进程存活。`GET /readyz` 需要 bearer 凭据；只有服务返回 HTTP 200 和 `ready: true` 时才能作为流量就绪信号。就绪不等于账户偿付能力、行情源可信或外部成交对账成功。行情陈旧时继续监控存活，但停止新增风险；恢复后仍需核对价格版本及未完成订单。

systemd 示例见 [deploy/uta.service](../deploy/uta.service)。安装前核对 Python 安装位置和凭据所有权，使用 `systemd-analyze verify deploy/uta.service` 检查本机 systemd 兼容性，再由管理员安装和启动。示例不会配置 TLS、负载均衡或自动发送订单。

## 备份

运行中禁止仅复制 `exchange.sqlite3`：已提交事务可能仍在 `-wal` 文件中。使用 SQLite online backup API 获取一个包含所有表的事务一致快照。目标目录应事先创建、权限受控、与数据库有独立故障域。命令不覆盖已存在文件：

```sh
/opt/uta/venv/bin/python -m uta.ops backup \
  --database /var/lib/uta/exchange.sqlite3 \
  --output /srv/uta-backups/exchange-20261114T120000Z.sqlite3
/opt/uta/venv/bin/python -m uta.ops check \
  --database /srv/uta-backups/exchange-20261114T120000Z.sqlite3
```

备份在同一目标目录创建权限为 `0600` 的临时文件，完成 SQLite 完整性和外键检查，刷盘后以不覆盖方式发布。成功输出 JSON，包含文件字节数、SHA-256 和表名。默认超时 30 秒，可使用 `--timeout` 调整至最多 3600 秒。不要把不完整临时文件计入成功备份。文件加密、异地复制、保留期限、备份调度和告警需要部署方配置。

备份中可能含客户数据，按数据库同等级别保护。保存命令输出、备份时间、软件版本、行情版本和当时已消费的事件游标。定期在隔离目录恢复演练，并核验账本重放、余额、持仓、订单占用及外部成交。`uta.ops check` 只检查 SQLite 结构和外键，不验证业务账本与外部托管资产一致。

## 故障处理与离线恢复

1. 检测到 I/O 错误、磁盘将满、未知成交、风险数据不完整或对账差异时，停止新订单并启用交易开关；保留进程日志和数据库文件。开关不能撤回已对外发出的订单。
2. 先停止服务及所有会写入此数据库的进程，保留当前数据库及关联 WAL/SHM 文件的取证副本。不要删除 WAL 来解决锁或损坏问题。
3. 校验备份的 SHA-256 和 `uta.ops check` 结果，恢复到一个从未使用的新路径。命令拒绝已有数据库及同名 SQLite sidecar，避免覆盖运行中的数据。

   ```sh
   /opt/uta/venv/bin/python -m uta.ops restore \
     --backup /srv/uta-backups/exchange-20261114T120000Z.sqlite3 \
     --database /var/lib/uta/recovered.sqlite3
   ```

4. 使用与备份兼容的软件版本离线核验恢复后的分录、事件顺序、订单和占用。先从备份水位向前重放或对账所有托管资金变动与成交。恢复旧数据库会丢失备份后保存的幂等键；在完成外部执行器和消费者水位对账前，禁止重放外部写操作或恢复交易。
5. 更新服务数据库路径，在暂停新增风险的条件下启动。发布新鲜行情，验证认证、账户隔离、风险结果和恢复水位。审核人完成对账签字后再恢复接单，并持续观察重复事件、旧订单与余额差异。

备份时刻决定数据恢复点；本项目没有承诺 RPO/RTO。幂等键只在保留其历史的数据库内有效，不能跨数据丢失自动保证外部副作用只发生一次。不要让原数据库和恢复数据库同时接单。

## 预发布验收

CI 在 Python 3.10–3.13 运行测试、演示、有限状态枚举、编译检查、wheel 构建和离开源码目录后的安装 smoke。每次部署需要保存所用 commit 对应的运行结果，而不是引用其他版本的测试数。

使用合成资金，至少完成下列检查并记录预期值及结果：

| 检查 | 可接受行为 |
| --- | --- |
| 多连接同时争用剩余保证金 | 接纳及预留在同一事务中，不能重复占用 |
| 相同订单、成交和充值 ID 重试 | 相同内容不重复生效，不同内容报冲突 |
| 本地部分成交与撤单竞态 | 成交不超量；已结算部分和剩余占用可核对；外部撤单确认仍需适配器 |
| 过期、未来或回退的行情版本 | 不接纳依赖失效行情的新风险 |
| 客户越权或错误凭据 | 无法读取或修改其他账户，管理员入口不可由交易员调用 |
| 事务期间杀进程并重启 | 已提交状态恢复；未提交资金、占用和事件一起回滚 |
| 数据目录无写权限、磁盘满或数据库忙 | 明确失败，不返回虚假的接单或记账成功 |
| 备份恢复及消费游标重放 | 水位可对账，消费者按事件 ID 去重 |
| 长时间持续负载 | 为本机测量 p95/p99 延迟、锁等待、WAL 增长和磁盘余量，确定容量与告警阈值 |

运营还应监测认证失败、错误率、响应延迟、行情年龄和版本、交易开关、对账差异、待处理事件滞后、备份年龄及恢复演练结果。不要把负债、私密余额、token 或完整请求体写入公开日志。

## 仍需完成的上线工作

本版本已提供本地双侧撮合、显式资金池借贷/利息、现货冻结和完整线性部分清算合成链路。仍缺外部交易所/托管适配、真实行情源、提现、资金费及自动利率调度、借贷强制处置、完整 PM、保险基金/ADL、跨分片结算、高可用复制和灾难自动切换。费用与风险参数还需真实产品校准、历史回放、外部逐笔对账、持续容量、独立安全与金融签核。生产门槛以 `docs/acceptance-gates.md` 为准。
