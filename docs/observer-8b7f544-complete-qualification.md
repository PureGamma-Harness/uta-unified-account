# 8b7f544 完整验收原始失败与收集器修复

结论：**NO_GO**。本证据集只确认原始结果和来源完整性；未重新运行 CI、单元测试、服务、SQL 或压力负载，没有上线授权。

源提交为 `8b7f544fcbdfd540d43de1d6560022c6ebbd3799`。PR 测试的临时合并提交为 `5cdc9b5abbd6ad86fb031512890d7b685219f8a6`，父提交为 `87e9f17359d5e67fd898abc31272ba5508a2c64d` 和源提交。两者 Git tree 均为 `1cb857b6e95444b89ccfbb873b97d1f23bccf77a`。GitHub 插件返回的 commit 对象没有 tree/parents 字段，因此另用 `gh api .../git/commits/<SHA>` 读取并保存这些窄字段。

## 原始结果

每行均执行 **1472 项测试**，每行均有 **1 项失败**，不是 1472 项通过。三次本地运行顺序固定为 3.12、3.10、3.13，绑定 CPU 1，与原长稳作业同宿主；这不是独占硬件性能结果。保留各自完整 `summary.json`、`worker-result.json`、`unittest.txt`，以及本地启动日志、矩阵进度/总结和原始外部 driver。

| 运行 | Python | 失败 | 错误 | summary 内测试秒数 |
| --- | --- | ---: | ---: | ---: |
| 本地 | 3.12.14 | 1 | 0 | 283.552061507 |
| 本地 | 3.10.22 | 1 | 0 | 283.594136444 |
| 本地 | 3.13 / SQLite 3.46 | 1 | 1 | 284.453792255 |
| push `44095333582` | 3.10 | 1 | 0 | 268.530205008 |
| push `44095333582` | 3.11 | 1 | 0 | 226.640906443 |
| push `44095333582` | 3.12 | 1 | 0 | 271.022184143 |
| push `44095333582` | 3.13 | 1 | 0 | 271.690337699 |
| PR `44095344867` | 3.10 | 1 | 0 | 233.350657313 |
| PR `44095344867` | 3.11 | 1 | 1 | 201.499730900 |
| PR `44095344867` | 3.12 | 1 | 0 | 228.756816287 |
| PR `44095344867` | 3.13 | 1 | 1 | 230.563667476 |

时间字段保持原样；summary 的父进程计时和 `unittest.txt` 的 worker 计时边界有差异，未相互覆盖。每份 summary 的 263 个输入摘要逐一与未改动的源冻结目录核对，11 份输入映射完全一致；原始记录均显示前后跟踪源干净、源未变更。

所有失败均来自历史回放将旧原始结果中的 generator 摘要与**当前** `benchmarks/run_managed_benchmark.py` 比较。该问题须在新提交修复和复测，不能将本轮失败改记为通过。

额外错误位于 `test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`：

- 本地 3.13 与 PR 3.11：原始暂停阶段第 1367 行 `lease()` 读取出现 `database is locked`；finally 第 1501 行再次读取并掩盖了先前异常。
- PR 3.13：第 1349 行 writer probe 的 `BEGIN IMMEDIATE` 先出现 `locking protocol`；finally 第 1501 行再次读取并出现同样错误。

两条路径保留区别。原日志没有提供实际 SQLite 数字错误属性，不能把二者统称同一种 BUSY 码，也不能从日志推断某个唯一底层成因。这里没有补跑、制造错误或改变运行时分类。

## 原 ZIP 文件名碰撞及恢复

原收集器对名称 `uta-unit-validation-python-3.10` 等调用 `Path.with_suffix('.zip')`，使同一 run 的四个 ZIP 都写向 `uta-unit-validation-python-3.zip`。每个版本已经解压的三份原始文件仍各自完整；每个 run 只剩最后一个 ZIP。

这是收集器错误，不是测试或 GitHub artifact 失效。两个碰撞 ZIP 原地保留，摘要记录于 manifest：push 残留 ZIP 等于 provider 3.12 artifact `14333003508`，PR 残留 ZIP 等于 provider 3.13 artifact `14333293239`。

本次通过 GitHub artifact 插件重新获取同八个 artifact，在全新目录中按 `artifact-<ID>.zip` 唯一命名。八份均满足：provider 原始字节数和 SHA-256 一致、ZIP CRC 通过、恰好三份原 members、所有 members 与原解压目录逐字节一致。完整 provider 元数据及结果 manifest 已入库；八份 ZIP 原件保留在私有本地目录 `/workspace/uta-ci-8b7-original-zips-unique`，没有新增二进制归档到 Git。未触发 CI rerun，未保存或发布临时签名下载 URL。

## 重复核验

在含本证据的新工作树中执行，指定原始且干净的 8b 冻结目录：

```sh
python evidence/runs/observer-qa-8b7f544-complete/verify_integrity.py \
  --frozen-source /workspace/uta-observer-freeze-8b7f544 \
  --original-zip-root /workspace/uta-ci-8b7-original-zips-unique
```

`--original-zip-root` 可省略；省略时仍逐项校验已提交的原始文件、263 项源摘要、失败结果和 PR tree 来源，但不会声称复核私有 ZIP。实际核验原始输出保留在证据目录。`integrity_passed=true` 仅指这些字节和来源检查通过，`qualification=NO_GO` 及 `production_approved=false` 始终保留。

## 部署与回滚边界

本提交仅新增证据与只读文件检查器，不修改运行时、产品规则、数据库、API 或部署配置，无数据迁移。无需部署；回滚可撤销本证据提交，不能删除或改写原失败、旧冻结源、运行中的实验、原 ZIP 或其副本。后续修复使用新的冻结 SHA、完整测试与独立复核，不能承接本轮不存在的通过资格。
