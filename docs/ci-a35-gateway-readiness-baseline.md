# a35 grouped HTTP / readiness：原始失败与待验证假设

独立修复基线为 `a35fd56fc98126b3e5cced8a459bd04ca580e537`。原 push Python 3.13
CI artifact 的 SHA-256 为
`a4c33a2cd5691f05d5e459cdf806ed23063f25cf133ca5e8e28ffeeae15ef671`。
完整原 ZIP、summary、worker-result 和 unittest 原文保留于
`evidence/runs/ci-a35-gateway-readiness/original-push-python313/`；ZIP 与解压文件
字节对应，227 个 source-before/source-after hash 一致且全等独立冻结源码。
原结果为 1243 项、2 FAIL、0 ERROR。其 NO_GO 永久保留，不重跑原 CI 来覆盖失败。

## 已知事实

1. `test_full_original_id_flow_accepts_an_actual_running_unknown_reply` 的真实 HTTP
   顺序为 `503 command_result_unknown` → `503 admission_queue_timeout` →
   `503 admission_overloaded`。现有有限客户端 helper 只允许前两种，因第三种失败。
   `admission_overloaded` 已在接口规则中声明为未入队、退避后使用原业务 ID；它不表示
   已接纳。原 HTTP 等待 50ms、客户端完成请求后检查的观察预算 3 秒均不改变。
2. `test_delivered_ready_frames_cannot_override_future_or_stale_market` 在
   `all(row["owner_ready"])` 失败。原 trace 没有保存该次 report、具体 offset 或原生
   lease 状态，因此不能认定唯一历史原因，也不能先称为普通 fixture 失败。

## 精确假设与取证边界

- H1：允许的队列满返回遗漏于测试 helper，可通过自有、真实有界队列和 HTTP 响应
  给出确定性反例；修正只能扩展到这个明确错误码，以原 method/path/content 重试。
  原 CI 未记录队列/存储快照，不推断为何恰在该时刻排队或变慢。
- H2a：mutex/control/shard 诊断预算到期可能使 owner/lease 未观察，默认
  `owner_ready=false` 是安全 unknown。H2b：真实 native lease 过期、owner PID/
  generation 或 READY-frame 不匹配也会得到 false。这些情况必须区分。
- `diagnostics()` 先读控制状态、原生 lease 和 guard，末尾再次按原生时钟核 lease，
  然后计算 owner_ready，最后才用父 datetime 检查 market freshness。源码中父
  datetime mock 不直接修改原生 lease 时钟；这不能单凭静态顺序判定原失败相位。

首个小范围计划仅运行原两个 case，并对原 diagnostics 作 call-through 观察，记录
安全的诊断 phase/timeout/elapsed、state_observed 和 worker lease/owner/report 字段。
不替换生产函数结果，不在诊断中创建服务或写 lease，不把新观察回填成旧 CI 原因。
本地可用 Python 3.13.5/SQLite 3.46.1 不等于 CI 的 Python 3.13.18；即使复现或通过，
也分别报告。CPU 3 和 <=30 秒总预算由集成负责人协调后才执行。

## 不能采用的修法

不扩展生产 TTL、HTTP 等待、诊断预算或行情新鲜度；不伪造 receipt、READY 或 native
lease，不将 unknown 当 true，不宽泛重试所有 503，不跳过 owner/lease 断言。真实
过期、锁竞争、不可观察和明确业务拒绝必须保持失败/拒绝。若需要 runtime 修复，先
报告独立 blocker，不能借测试修正隐含改变生产策略。

之后的 test-only 改动与真实负控、红绿原件单独追加。此初始归档未执行目标测试、
SQL 或服务，不宣称解决问题、完整 release、性能或生产验收。回滚仅恢复测试/文档，
不迁移或改写任何金融 authority；部署准入仍由集成负责人和另一组审查决定。
