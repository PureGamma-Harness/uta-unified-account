# PR48 首次 CI 证据

[PR48](https://github.com/PureGamma-Harness/uta-unified-account/pull/48) 的首次 push 与
pull_request 检查均失败，不能称全绿。以下为待另一工作组独立 RAW 复核的有限 SAFE
采集结果；不重跑 CI，不用本地 SQL PASS 覆盖本次失败，也不推导生产资格。

源码 C 为 `6ba5ba2e9334f30be949f368d036c96fe9857c30`，base 为
`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`。PR merge
`e211e4b3d2b7e91db54a45baaae2cfd73331f539` 的父顺序为 base/C，tree
`6ead209181fded3d164aa70a57bd2c928f0c73f8` 与 C 相同。

| 首次 run / attempt1 | 整轮 | 矩阵 job | 已取失败单元报告 |
| --- | --- | --- | --- |
| [push44283600389](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44283600389) | FAIL | 3成功、Python3.12失败 | 2055 tests / 1F / 0E / 0skip |
| [PR44283882268](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44283882268) | FAIL | 3成功、Python3.12失败 | 2055 tests / 3F / 0E / 0skip |

采集者首次实际 batch clock 为10:26:57 UTC，届时两次 run 都已终态，因此每个 run
只采样一次，没有后续 poll。provider 更新时刻分别为10:23:17Z、10:25:28Z；没有把
此前 root 提供的未完成状态冒作自己的采样，也没有制造固定30秒 cadence。

## 精确失败阶段

push 的唯一失败是 `test_market_probe_rejects_a_real_expired_owner_lease_without_retry`：
`tests/test_readiness_sampling.py:253` 在预期 inactive-lease 异常已被捕获后，检查
`observed.call_count` 为1，实际为4。失败原件没有保留全部四次观察的内容，不能据此
断定为何多次调用或归因于某个锁/调度点。

PR 有三项失败，分别保留：

- `test_clock_rollback_detects_future_without_relabeling_prices` 在 `activate()` 的
  `tests/test_process_readiness.py:75` 清除 halt 时仍为True，尚未进入 clock rollback。
- `test_bounded_eventual_observation_cannot_pass_partial_or_actual_stale_quotes` 在
  `tests/test_readiness_sampling.py:358`：有意争用的 fence 释放后，同 SID1 重发仍为
  publishingTrue / market_fanout_incomplete，尚未到后续 SID2 或坏行情循环。
- 同名 expired-owner-lease 测试在 `:251` 的期望异常 regex 失败；原内层消息为 READY
  report 的 pid 与当前 native owner pid 不一致。仅保留关系：READY report generation 早于当前 owner generation；这与 helper `:79` 的身份前置检查一致，未到 `:253` 调用计数
  断言。实际 PID 与完整 profile 不公开。

底层运行时原因均记为 **UNDETERMINED**。不把它们合并成旧 SH 捕获/五秒恢复失败，
不据新资金费方法通过而证明资金费变更绝无时序影响。源码与逐项 header/选定 assertion
行的 SHA 记录在 `failure-phase-projection.json`，完整日志留私有原件。

## 新六方法与固定正样本

预先固定的 PR Python3.13 job `134731389281` 成功，取得 unit artifact
`14418413338`：2055 tests、0F/E/skip/EF/US。两个失败 Python3.12 bundle 和这个固定
正样本中，新 `FundingArithmeticTests` 三方法、`FundingLocalSQLTests` 三方法，每个
均有一次实际 ok 行，共6个唯一 ID / 18次观察。其余成功 job 只保元数据，不声称逐方法
下载验证。三份报告的 baseline worker 都是精确原生7字段，与 summary 逐类型和值一致。

三份单元报告各371个 before/after 源指纹相同并逐 Git C 核对，原日志 SHA 也一致。
push code_commit 为 C，PR 为上述等 tree merge。失败运行时是 Python3.12.16/GCC15.2.0/
SQLite3.46.1，正样本是 Python3.13.18/SQLite3.46.1；均不等同本地3.12.14/Clang22.1.3/
SQLite3.53.1。普通 CI 六方法没有运行本地独立 once wrapper、额外 RO 设置或离线字节
参考解析器；CI 临时 DB 未在这些 bundle 中归档，不能借本地保存库来代替它们。

同一固定 PR3.13 slot 的 small package artifact `14418113095` 保留提供方 report 成功：
七 checks 为True、64个 runtime 指纹匹配 C、6923个 required 路径含全部58个变更路径，
报告 sdist members6930 / missing0 / mismatched0；installed-report 记录八测试与八命令
exit0。installed 模块清单25个，未包括两个新增资金费模块。未下载 wheel/sdist，未独立
构建或安装，故证据级别是 **PROVIDER_SMALL_REPORT_ONLY**，full qualification 与已安装
资金费操作资格均为 null。正样本不能把两个整轮 FAIL 改绿。

## 原件、预算和回滚

只取得两份失败 job decoded log、两份失败 unit ZIP、固定正 unit ZIP及一份 small package
ZIP，各一次，无替代挑样、重下或 API/下载错误。四 ZIP 共28 members CRC通过。
全60份私有响应/ZIP/member/log/header/transfer 原件共2,715,344 bytes，均0600，目录0700，
低于64MiB总限额；unit均低于2MiB、report低于1MiB。PRIVATE-SEAL为12,768 bytes、SHA
`944b5c59d817b62199437940637ef5ff84b171ef2a51eda64b238d8ed868e9f5`。

公开仅有限结果、六方法原行 SHA、失败阶段有限关系和长度/SHA清单。原 ZIP、member、
完整 unit/decoded log/profile、HTTP headers、signed references 一律留私有；不导出 DB、
完整源码 capsule、nonce、wheel 或 sdist。本次未执行目标、SQL、PID/proc 探针或 benchmark。

此提交仅追加证据和说明，没有金融代码、schema、账户权威、模式或阈值变更。部署为
合并这些有限报告；回滚可撤销本证据提交并继续保留首轮私有原件，不清理数据库或改写
旧结果。独立 RAW、故障/稳定性/容量、DUE/scheduler、opsAuth/custody、managed/HA、人类
金融签字及真实资金上线审批继续 OPEN。
