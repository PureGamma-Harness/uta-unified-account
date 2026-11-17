# 固定源码 7200097：完整工程验证

发布源码为 `7200097ce9f92fa678907bee9a99933f60d65bc3`，冻结树
`/workspace/uta-durable-final-7200097`。以下是该源码的实际结果，不能外推到后续运行时改动。

| 本地环境 | SQLite | 实际完整 tests | 结果 |
| --- | --- | ---: | --- |
| Python 3.12.14 | 3.53.1 | 916 | 通过，128.891s |
| Python 3.10.22 | 3.53.1 | 916 | 通过，133.065s |
| Python 3.13.5 | 3.46.1 | 916 | 通过，134.474s |

各次 summary 记录实际命令、OS stdout/stderr 日志摘要及前后 source hashes；
失败、错误、跳过、expected failures、unexpected successes 均为零，源保持 clean/unchanged。
日志未观察到 `ResourceWarning:`。这不是所有环境下无资源泄漏的证明。

同一 source 的 GitHub [push run 44025608750](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44025608750)
和 [PR run 44025613936](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44025613936)
各有 Python 3.10/3.11/3.12/3.13 四个成功 job，每个实际 916 项。
本目录保存两个 run 的全部 job/step 状态及八份 connector 解码日志，未观察到 ResourceWarning。
CI 后续实际 acceptance、形式模型、wheel 和安装入口步骤也成功；这八个 job 是两次独立 CI 执行，
不拼成一次更长的容量或稳定性测试。

复跑：在相同固定源码的新干净工作树执行
`python tools/run_validation.py --output /absolute/new-result-directory`。
每个环境必须使用自己的新结果目录。构建/安装结果另见
[发布包证据](../../20261117-package-7200097/README.md)；旧 284 包的四项遗漏与原预检失败原样保留。

本次没有复制、多可用区、真实资金或 10,000/s 持续容量验收。
原 887 的独立历史 24 小时任务也不授予该 managed 候选稳定性资格。
`production_approved=false`；真实负责人签核及对应产品启用仍被门槛阻断。
