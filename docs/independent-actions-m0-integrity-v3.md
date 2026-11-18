# M0 控制器 v3：关闭 e444 数据完整性否决，尚未执行

本修复以 e44493f67846adbdee0ff1064743cd1444c5cb4e 为原控制版本，完整 cherry-pick 独立 VETO OWN `07a90741ff1b3a508a3a07da43685514319a4f06` 为 `b83b80728a3a019d1acf4e5e72a8a3c8eaabe443`。原 49 PASS、独立两个正例和 8 RED、首次 helper cwd 错误均保留原字节；旧结果没有被改称通过。原始报告见 `docs/independent-actions-m0-e444-review.md` 及其 evidence/reviews 路径。本控制修复仍待独立组对固定提交重新审查，不等于远端执行 GO。

## 数据口径与边界

`project_summary` 将 outcome_counts、counts、只读重开成功数及 ACK 数闭合。金融成功、业务拒绝及控制/行情拒绝之外的技术/unknown/timeout/late 非零即拒。整数排除 bool；数值拒 NaN/Inf；计时非负且 elapsed 至少为固定 10 秒；吞吐分别严格核金融接纳数/elapsed、ACK 数/elapsed，float 比较 rel_tol=2e-12、abs_tol=1e-12。

`project_arrivals` 逐行读取 gzip，每次最多 min(65,537,remaining+1) 字节，在 JSON 解码前检查单行 65,536 字节及总解压 8 MiB；不先整文件 decompress。200 个唯一序列与原命令 ID、receipt.command_id、终态类别、ACK/start/call-finish/completion 顺序、latency=completion-planned、固定 1 秒 deadline 均检查。`verify_population` 将全部 200 行与 summary 的独占结果及金融/ACK/late 人口闭合，并验证 20/s 的计划时间序列。

真实 source909 `benchmarks/run_managed_benchmark.py` 的 750–796 行以 settled-start 定义 elapsed、包含回执观察 drain，startup/close 排除；新的 footer 校验将该分母绑定 `measurement-footer.json`，不能任意填更短 elapsed。source909 `benchmarks/run_benchmark.py` 的 `LatencyHistogram` 为 log1p 宽度 0.001 的 ceil 上界桶。按完整原始 ns 人口独立重建 nearest rank（整数分数 1/2、95/100、99/100、999/1000），允许 reported_ns 在 exact_ns−1e-6 至 exact_ns×1.001+2+1e-6；2 ns 覆盖 ceil/浮点边界。只验证该公开桶误差界，不宣称重建了逐桶原始字节或无限精度分位数。

## 独立 owner、完整 case 预算

父控制器使用 source909 原 `tools/run_managed_variants.py::owned_run` 启动一个全新 session 的 case-worker，显式一个 allowed CPU，56 秒 watchdog、TERM 最多 2 秒、KILL 等待最多 2 秒，原 pidfd/未回收 leader/session 身份核验和保护旧 PID 规则保持。case-worker 内从控制/源核验开始，完成 driver、解析、跨文件/时钟检查、source 再核、profile 语义导出、全部安全输出 hash/fsync、原子目录发布及 completion 记录；这些步骤均在独立父 owner 监管下。driver `start_new_session=False`，两个真实 spawn owner/native 子进程继承新 session，避免 nested session 脱离外层清理。实际拓扑为监督控制器 → case-worker → 1 driver → 2 spawned owner/native；负载仍为 2 shards 和一个 CPU，新增 case-worker 不改变 workload argv。

case-worker 仅接受新建 0600 同 UID descriptor；检查活父 PID/birth ticks、source/controller/hash、host/boot、实际新 session 及单 CPU。它是已获根批准父进程的内部能力传递，不是新的批准接口，同 UID 恶意改代码不在此权限模型内。provider token 不传入 case-worker 或 driver。

父进程在返回后只收集 ≤64 KiB completion descriptor，并对含 descriptor 准备和收集的完整 case 再验 ≤60 秒。超时仍 UNKNOWN；部分发布移回 private quarantine，不删除首字节，P 明确 NOT_RUN。独立 owner 处理过程超时，最终 elapsed 检查处理最后控制收集已超预算；纯桩不证明真实 OS 调度/不可中断磁盘 I/O 能在物理 60 秒内清理。没有 OS 磁盘 quota 或绝对硬实时声明。真实独立 runner 仍需验首次 timeout/cleanup 行为后才可采信。

全局 source 初次与末次 5518 文件 hash、host 元数据、WAL/FULL 短探针及最终全公开文件核验/upload 属于 job 级步骤，受 6 分钟 job timeout，独立于每 case 的已声明结束点。每 case 内仍重做 source909 全文件/当前字节核验，未用 cache 弱化数据或代码变化拒绝。case 32 MiB 包括 private 本体、已发布 case 安全文本、context 与 case-owner logs；aggregate 64 MiB、cleanup 32 MiB、额外 free 2 GiB 与 fresh-free 2,214,592,512 字节门槛保持，均是观测门槛而非物理配额。workspace 19,662,897,152 字节 cohost 预算不降低。

公开结构新增固定 `case-B-safe/` 和 `case-P-safe/` 两个目录；完整 manifest 精确列文件/hash/大小、拒 symlink/special/unlisted 文件。两个原 workflow 仅同步新增纯测试和 `**/*.json` 安全上传路径，原 dispatch-only 设计仍留 Git 历史；专用 once branch/首次 creation/attempt1/sole manifest child C→M 限制不变。无 marker、M、push 或 dispatch。

## 测试、证据及下一门槛

新纯合成测试保留原 8 个变异，覆盖 gzip 单行/累计上限、禁止整文件 decompress、footer 分母、量纲与 bool、错误分位数人口、独立 owner 包含 parser/hash/fsync、最后处理超过 60 秒、UNKNOWN 私有保留及完整 manifest。原 49 测试不改。中间诊断 stdout/stderr 原件均保留；初始 17 新测在旧 parser 下的首红含 12 failures/3 missing-new-join errors，其运行时尚未建立完整 source-bound runner，因此不冒称该诊断输出具备最终审计资格。独立原 8 RED 有其完整 immutable source-bound 证据。最终测试另记录精确源码 SHA、命令、时间与全部原始 stdout/stderr，无 SQL/product/native/profile/Actions。

本提交仍是 `safe_projection_private_ephemeral_R&D_only`：并未保存完整原 stdout/stderr，private 原 streams 只在 runner 生命周期存在，不满足最终 durable raw 交付。root 已选择 option B（只加密 stdout/stderr）作为下一独立代码提交；本提交没有读取任何私钥或实现/假称 CMS。不得用此版本做实际远端 M0，必须等 option B 实现与独立审查后重新给具体 GO。M0 最多 R&D，不是 10k/s×30min、清算成交或 HA/生产资格。

回滚：不登记/不推 M，保持当前 source909 和旧运行任务；若未来做候选修复则新 C/new evidence，原首失败不重跑覆盖。
