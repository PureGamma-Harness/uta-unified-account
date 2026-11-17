# 预检与调查：保留失败的完整记录

这些记录不是当前最终候选的发布资格，更不是生产批准。源代码、测试数、解释器和结果按各次运行区分。

* `../durable-acceptance-89bd349/`：固定 `89bd349` 的三次完整验证，Python 3.10.22 / 3.12.14（SQLite 3.53.1）与系统 Python 3.13.5（SQLite 3.46.1）各 894 项通过，失败、错误和跳过均为零。摘要含原始源文件、日志摘要和实际运行时间。
* `python312-8eeab43/`：固定 `8eeab43` 的本地完整 899 项验证，1 项即时 readiness 断言失败，`passed=false`；没有保留该次完整诊断，不能事后断言唯一根因。
* GitHub push run [44018824285](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44018824285)：同一 `8eeab43`，3.10 的历史 PID 故障注入遇到 `ProcessLookupError`，3.13 的 benchmark 启动即时诊断失败；3.11 和 3.12 成功。两份失败日志与全部 job/step 状态保留。
* GitHub PR run [44018901056](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44018901056)：同一候选四个 job 各 899 项成功。3.10.22 / 3.11.18 / 3.12.16 / 3.13.18 的 SQLite 均为 3.46.1，测试时间依次为 130.649 / 127.393 / 137.039 / 114.703 秒。**3.13 的成功日志包含两个 ResourceWarning**，不宣称无警告。四份日志是 connector 返回的解码文本归档，非 GitHub 原始压缩文件。
* `focused/`：确定性 READY 采样/benchmark 启动与 orphan 身份握手的独立复核。原始不安全随机停止试验的开发失败也保留。所有具体范围、命令、源文件摘要和局限见 [readiness](../../../docs/readiness-sampling.md)、[orphan](../../../docs/orphan-harness-validation.md) 与 [性能](../../../docs/managed-performance.md) 文档。

修复保持生产 readiness 保守、原业务超时和 .6 秒测试租约；父缓存尚未收到真实 READY 时不能仅凭激活回执认定已就绪，历史整数 PID 也不能用来注入信号。最终候选必须重新执行完整验证及远程矩阵。`archive-manifest.json` 记录本目录归档文件摘要；后续补充证据需明确新的源提交，不能改写本次结果。
