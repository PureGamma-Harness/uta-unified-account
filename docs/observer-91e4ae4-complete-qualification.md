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

## 完整 CI 原件核验

两个 run 的八个 jobs 均已自然结束：七个 success，一个上述 failure。八份 unit 的原始 summary、worker-result、完整 unittest 输出均已归档，全部实际执行 1512 项、零跳过，七份通过，一份失败。八份的 266 项源输入摘要逐项与同一冻结源核对，完全一致；所有原始记录均为源未改变且前后跟踪源干净。

七份 package-validation artifact 各自恰有 19 份文本/JSON 原始 members，全部已归档，包含原 package manifest、fresh isolated installed-report、八项 console 测试与八个真实 CLI 命令输出。报告均为对应 job 实际产生，PR 包的 `source_commit=d7f23ca...` 保持原值，未改记为源提交。七份原报告各自七项 archive 检查通过、52 个 runtime 文件一致、3633 个 tracked 文件齐备；fresh isolated 安装各有八项测试零失败、零错误、零跳过，以及八个 CLI 命令退出 0。

全部 22 份 provider ZIP 按 `artifact-<ID>.zip` 保存在 `/workspace/uta-ci-91e4-original-zips-unique`：每份原大小、SHA-256 与 provider 一致，CRC 全部通过。七份 wheel artifact 内各有实际 wheel 与 sdist，均与**同 run、同 Python job** 的 package manifest 及 installed-report 的字节数和 SHA-256 一致。另以只读文件计算独立核对七份 sdist 内各 3633 个 tracked 文件和七份 wheel 的 52 个 runtime 文件，均逐文件与冻结源一致。wheel/sdist 二进制不发布到本证据提交。

运行时树摘要保留为 `e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792`。这些完整性检查和七份包通过不能弥补第八 job 的失败，也不能声明完整 CI 通过。

只读核验命令不导入生产核心、不运行测试、服务或 SQL；`--original-zip-root` 省略时只核验已提交原 members、来源和结果，不声称重新核验未提交 ZIP。

```sh
python evidence/runs/observer-qa-91e4ae4-complete/verify_integrity.py \
  --frozen-source /workspace/uta-observer-freeze-91e4ae4 \
  --original-zip-root /workspace/uta-ci-91e4-original-zips-unique
```

实际核验输出记录 `integrity_passed=true`、22 份 ZIP 与七份完整 sdist 文件核验通过，同时保留 `qualification=NO_GO` 和 `production_approved=false`。本地三次原始运行还在按原顺序执行，将在原矩阵自然完成后追加封存；当前未完成的证据不能当作通过。
