# 91e4ae4 验收原始证据

当前结论为 **NO_GO**。本提交只收集原始文件与来源元数据，不重跑 CI、不修改冻结源、不改变验收门槛。

## 已确认阻断：push Python 3.13

push run `44104161669`、job `134111871255` 在 `Run unit tests` 步骤失败。原 artifact `14337038689` 的 provider 字节数为 62774，SHA-256 为 `fc322033545aa56890c5ee760a22d7c3879f8ebd48ba6c055896f378b2291b40`。原 ZIP 以唯一 ID 文件名保留，CRC 通过，三份原始 members 已逐字节归档。

原始 summary 记录 1512 项测试、1 项失败、0 错误、0 跳过，`passed=false`，输入摘要共 266 项，逐一与未改动的 `91e4ae40b5e9b884c54026406299df5000c9c100` 冻结源一致。

唯一失败是 `test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`，位于 `tests/test_durable_faults.py:1525`：原绑定 PID 未在原定五秒恢复期限内退出。该结果与旧轮次的 BUSY/locking-protocol 异常不同。原日志没有足够的状态事件说明本次未及时退出的唯一根因，不能推断为某个既定原因，也不能将后续清理等同于期限内恢复。summary 父进程计时为 284.648566440 秒，worker 原日志计时为 282.765 秒，均保持原样。

其余七个 CI jobs 原始结果为 success，但不能覆盖这个阻断。失败 job 的 package 与 wheel 步骤被跳过，因此原 provider 实际只有八份 unit、七份 package-validation、七份 wheel artifact；不存在第八份包验收证据。

PR 实际测试合并提交为 `d7f23cac215ede34a4aa8e20014ecfc418912830`，父提交为 `87e9f17359d5e67fd898abc31272ba5508a2c64d` 和源 `91e4ae4`，tree 为 `aee09a50357f3c46d50910f03f722e3fcfc6af05`，与原源提交一致。源提交和 PR 合并提交身份分别保留。

## 交付边界

独立证据分支只新增合成测试输出、provider 元数据与核验记录。无数据库迁移、API/运行时或部署变更，无需部署。撤销证据提交即可回滚工作树；原始失败、ZIP、源冻结目录及仍在运行的本地矩阵和长稳作业均须保留。后续工程修复应使用新 SHA 独立复测，不能改记本轮结果。

完整八份 unit、七份 package 与 wheel 原件完整性、以及本地三次原始运行，将在相应原始文件完成后继续追加封存。当前未完成的证据不能当作通过。
