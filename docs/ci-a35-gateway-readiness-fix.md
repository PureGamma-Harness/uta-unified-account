# a35 grouped HTTP / readiness 定向修正

这是 test-only 交付：运行时、native lease、诊断策略、50ms HTTP 等待、行情新鲜度、
客户端完成请求后检查的 3 秒预算均未改动。原 a35 CI 的 1243 项/2 FAIL/0 ERROR
及完整 ZIP 保持永久 NO_GO。初始假设、227 源输入核对和原始摘要见
[原始失败归档](ci-a35-gateway-readiness-baseline.md)。

## 修正的可验证合同

`request_until_known()` 仅多允许已文档化的 `admission_overloaded`。它表示这次调用
未入队，按同一 method/path/order ID/content 退避重试；仍只有实际 201/200 才算成功。
UNKNOWN 与 queued cancellation 的原处理不变，其他 503 立即失败。原查询、重开、
接纳/撤单事件各一笔、预占释放、资金及分录断言均保留。

行情 freshness 断言现在要求**当次实际、完整的 owner 观测**。每个采样先断言
ready/financial_ready 为 literal false；原生 generation 未观察时，owner_ready 和
lease_active 也必须为 literal false。已经观察到 inactive native lease 第一次就失败，
已知 PID/generation/READY frame 不匹配也失败，不能等新一轮来掩盖真实风险。

仅明确诊断超时的不完整观测可在 1 秒总预算内重采，每次请求最多 100ms，沿用已有
wait_ready 的采样节奏，不扩展生产预算。有时一个 shard 已明确 future/stale、另一个
shard 明确 diagnostic_timeout，此时仍保留 false 并等待新的完整观测。最终必须真实
owner_ready、active native lease、funding verification 全部具备，并同时得到两 shard
的精确 market_future/market_stale 拒绝，才满足该测试的前提。预算耗尽仍失败。

## 红例、真实负控与安全清理

- 真实 running writer 加满有界队列，收到真实 HTTP overload 后才释放：原 helper
  确定失败；修正后以原身份提交一次业务效果，资金不变。
- 实际关闭 admission 的 HTTP 503 必须只请求一次并失败，不被宽泛重试。
- 首个真实 control lock timeout 产生未知 owner，原单采样 owner=true 断言确定失败；
  修正后完整采样重新证明 native 状态，不给原 unknown 填 true。
- 持续 control 争用的负控始终保持 ready/financial/owner/lease false，有限预算不能通过。
- 只暂停本次自有、已用 PID/birth 和 pidfd 绑定的 worker，原 1 秒 native lease 实际
  失效后，helper 第一次就拒绝。硬保护原作业 PID，暂停前持真实 gate 与空闲 SQLite
  writer 确认无在途事务；没有调整 native gate、TTL 或生产 supervisor。

原 RUN-B 为 **2 FAIL / 2 PASS / 1 ERROR**，不能改写成通过。第⑤确实观察到 inactive
lease，但原 supervisor 已回收旧 owner，cleanup 的 proc 读取失败；原件没有 pidfd
terminal poll，不能事后补证。新 cleanup 只在绑定 pidfd 的 POLLIN 证明旧 owner 已退出
时记录终态、不发 SIGCONT；否则先匹配同一 birth 后用 pidfd 恢复同一 owner。proc
不可知且 pidfd 未证退出仍失败，绝不恢复未知/替代 PID。原 fixture cleanup 继续关闭
它的全部当前 children。两次 RUN-C 实际均记录旧绑定 owner 已退出、resume_sent=false。

## 实际执行与限制

| 原件 | 实际 source | 范围/结果 | 墙钟 |
| --- | --- | --- | ---: |
| RUN-A，3.13.5 / SQLite 3.46.1 | `3772aa8` | 原 2 case，2 PASS，NOT_REPRODUCED | 2.735s |
| RUN-B，3.13.5 / SQLite 3.46.1 | `f164ed0` | 5 个合同/负控，2 FAIL、2 PASS、1 ERROR | 6.147s |
| RUN-C，3.13.5 / SQLite 3.46.1 | `1a9d6f4` | 原 2 + 新 5，7 PASS | 7.410s |
| RUN-C，3.12.14 / SQLite 3.53.1 | `1a9d6f4` | 同 7 case，7 PASS | 7.780s |

各阶段只有一次经批准的 CPU3 小范围执行，28 秒 worker + 2 秒自有 cleanup 配置，均未
触发外层超时。两次 RUN-C 顺序执行，共约 15.19 秒，属于不同解释器/SQLite 验证，
不能相加声称 14 项不同案例。测试前后输入哈希相同，完整命令、原始 trace、结果及
版本见 `evidence/runs/ci-a35-gateway-readiness/`。本地 3.13.5 不等于原 CI 3.13.18。

RUN-A 没有复现原 readiness 失败。新 control-timeout 反例证明一种兼容机制，不证明
旧 CI 就是这个唯一原因；若新 CI 暴露真实 native 失效，本修正仍会拒绝。没有运行或
重跑原 CI、完整套件、压测或 long run，未接触原作业/observer/live SQLite。

跨组审查与新 source 的实际完整 CI 必须另做。本次不授予完整 release、容量、HA 或
生产资格。部署仅更新测试/证据，不迁移数据库；回滚恢复测试即可，保留已有 CID 与
未完成义务，不改写金融 authority 或原失败证据。
