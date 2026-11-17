# 激活事务与父进程 READY 观察

本次调查保留 root `8eeab43` 的本地完整验证失败：899 项中，`ManagedProcessFaultTests.test_real_worker_quarantines_persisted_poison_and_then_processes_same_account_cancel` 仅在 `active()` 的一次即时 `diagnostics()["ready"]` 断言失败。原始 log 没有该次 observation，因此不能精确证明它来自 READY pipe 延迟、诊断 deadline、SQLite busy、真实 owner 变化或其他条件。其他 runtime/CI 的成功不能补造这次缺失的证据。本次没有修改 production readiness、缓存、行情、租约或 financial helper。

原 raw log 位于 `/workspace/uta-durable-validation/final-merged/python312-8eeab43/unittest.txt`，SHA-256 为 `6d3e07d9fd3ce311bee250d69b5e5506e6ccde3b2f72291648134184a942caeb`；对应 summary 为 failures=1、errors=0、skipped=0、passed=False。它没有因本次 focused 成功而被改写。

## 可确定复现的交错

`tests/test_readiness_sampling.py` 只延后父 `_supervise` 消费 pipe 的调度，使用原故障测试的同一两分片 fixture。真实 spawn 子进程照常初始化、取得各自 PID token、续租并执行 publish/activation。两个 READY frame 确实已在 pipe 中，`pipe.poll()` 为 True；不是用内存假的 owner/report 代替真实金融命令。

实际观察保存在 `readiness-sampling-observations.json`，含原 runtime commit/file SHA-256 和前后完整诊断；合成状态中不含路径或 writer nonce：

| 字段 | 父 monitor 尚未消费 | 消费后 |
| --- | --- | --- |
| publish/activation | 成功提交 | 没有再次调用 |
| state halted/publishing | False / False | False / False |
| PID、generation、market digest/version | 同一组有效值 | 不变 |
| lease/market/funding/local activation | 全部 True | 全部 True |
| 父缓存 `report` | `{}` | `state=ready`，PID/generation 匹配 |
| `owner_ready` | False | True |
| overall reason | `worker_unready` | `ready` |
| `financial_ready` / `ready` | False / False | True / True |

原因是子进程在处理控制命令之前发送 READY，但父 monitor 大约每 50ms 消费一次；查询控制命令的 terminal receipt 不会同步刷新父缓存。`diagnostics` 是有界的一次观察，保守地拒绝尚未被父进程观察到的初始化握手。成功激活并不保证下一条采样已获得所有观察信息。这个受控 case 证明即时 True 假设不成立，**不证明原未记录失败的唯一原因**。

## 有限观察契约

原 `active()` 的 publish/activation 断言、每次业务等待 10 秒、1 秒 fixture TTL、轮询配置和金融条件均保留。只在诊断 reason 为 `worker_unready` 或 `diagnostic_timeout` 时，允许在独立、最多 10 秒的观察预算中再次执行完整诊断；每次给诊断的 timeout 也不超过剩余预算。未把缓存的 True 当作当前 True。

`market_stale`、`market_future`、`publication_incomplete`、`router_halted`、资金证明/身份错误，以及未明确分类的 `shard_unavailable` 等其他原因立即失败。截止后仍失败时输出最后完整 JSON observation。最终断言仍要求当前 `ready`、`financial_ready` 以及每片的 `owner_ready`、`market_ready` 全为 True。这里增加的是测试对异步观察的契约，没有扩展业务 deadline 或 writer lease，也没有为测试降低风险门禁。

四个新增实际过程 case 验证：

- 已真实激活但尚未消费 READY 时保守 False，随后同 PID/代次变 True。
- 已消费 READY 也不能让未来或过期报价变 True。
- 实际 router gate 争用可使一次诊断超时；释放后重新验证当前就绪。
- 实际部分发布与自然老化的报价不能被有限观察循环放行；完整发布/激活及更高版本新报价才能恢复 True。

## 调查与验证记录

原问题的 focused case 在保留即时断言、仅新增 failure JSON 的阶段：单次 1/1 通过（0.727s），随后三轮 3/3 通过（2.083s），没有捕获新的异常 reason。四个受控 case 首跑 4/4 通过（2.917s），并另行成功采集前后诊断。原 case 的自然失败概率并未由这几次成功量化或证明为零。

一次辅助 report dump 曾错误地用 stdin 作为 multiprocessing spawn 入口，触发 `<stdin>` 无法重新打开，最终由 10 秒 fixture timeout 清理；改用可导入的 unittest/`-c` 入口后采集成功。它是调查 harness 错误，不归为系统根因，也没有被算作通过样本。

最终将新增 4 项、既有 12 项 freshness/readiness 和原 poison case 合并 focused 验证：Python 3.12.14 / SQLite 3.53.1 为 17/17（12.380s）；Python 3.13.5 / SQLite 3.46.1 为 17/17（14.047s），后者启用 `-W error::ResourceWarning` 且无 warning。两组均无 skip。未修改 production 文件；保存 observation 的 runtime file hash 也与 `git show 8eeab43:uta/durable_process.py` 相同。

完整 903 项验证及 CI 由 root 在合入后执行。这里的 focused 结果不是新的完整验证通过报告，也不覆盖原 899 失败或授权长测。
