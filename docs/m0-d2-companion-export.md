# D2 companion 导出：新 SOURCE 的首 PURE 结果

最新状态：固定 SOURCE `8594a35827b0e064584113de48fda2490cb1c98e` / tree `ee5699814d37bbfb5d1ccb08e2c8bd5358f16fa3` 在 root 具体条件预算、独立 CODE_ONLY READY 与闭包核对后，首次一次 **76 PASS / 0 fail/errors/skips / exit0，CPU2，target child0**；外层 389,344,436ns，target计量 169,015,517ns，stdout0B / stderr12,384B。无重跑。首原件逐字节保存在 `first-pure-8594a35/`，当前状态另见 `current-status.json`；独立只读 raw 绑定复核已闭合（PURE_ONLY PASS）。此通过仅验证合成 capture/export 合约，默认 FLAG 仍 false、next_run_permitted=false，kernel backend 仍 NOT_IMPLEMENTED / NOT_VERIFIED，无实际GHA/M06/M05补录。

冻结 CODE 阶段的历史描述如下；其中“本轮未跑/待授权计划”已由上述唯一首 PURE 事实 supersede，冻结 policy/static-provenance 与原件不回写：

本轮实现一个默认关闭的持久 D2 companion，尚未运行本源码的测试、guard 或任何实际 workload。`D2_COMPANION_EXPORT_ENABLED=False` 是源码常量；环境变量、CLI、旧 marker 均不能启用。未来启用需要另一个明确审核并绑定 controller SHA 的 source，另授实际执行范围。本提交没有 M06 registration、workflow、namespace、push 或 dispatch 变更。M05 的 B UNKNOWN / P NOT_RUN、spent05、旧 D1 九字段及首 ERROR/PURE 原件均保持，不能用新代码给旧运行补造字段。

前一 source `3040d09b576009893c6630f3c19ef4ad35fd774d` 的首次 120 PASS（99 declared + 21 inherited）、CPU2/child0 及独立 PURE_ONLY PASS 保留在父提交 `5ae5299f858a47f7f8669e81314ee9e654ad631f`。该通过不覆盖本次导出代码。Kernel backend 仍为 NOT_IMPLEMENTED / NOT_VERIFIED；接口与 capsule 的解析正确性不等于实际物理 quota 证据。

## 固定 schema 与同源验证

唯一 public 名为根目录 `resource-scan-d2-{PHASE}.json`；PHASE 只能取原固定八个 diagnostic phases。私有 stage 是 `resource-scan-d2-incomplete-{PHASE}.json`。每个 capsule 至多 4096 B，顶层严格七字段：`kind=M0_RESOURCE_SCAN_D2_COMPANION`、整数 `version=1`、`phase`、`predicate_site`、固定 workload `source_commit`、当前完整 controller 的 `controller_sha256`、原严格 D2 `scan`。额外字段、重复 JSON key、NaN、错误 phase/source/hash 均拒绝。没有原私有路径、任意路径 hash、异常消息、key、nonce 或 opaque proof token。

`scan.elapsed_ns` 仍是原 deadline predicate 已读取的那一个值，不增添一次替代时钟读：C933_L377 的 POST_RETRY_SCAN_RETURN / LE 映射为 `AFTER_RETRY_SUCCESS`，仅表示那次 scan 返回成功后，随后 elapsed 门槛仍可能失败；C933_L382 的 QUALIFIED_AUX_ENOENT / LT 映射为 `AFTER_AUX_MISS`。两者都不是 case/business 成功标签。固定 catalogue 仍仅来自已认可的当前/上次辅助文件上下文，不推断 DB corruption 或失败根因。

`collect_resource_scan_d2_companions` 仅枚举这些固定根目录名，验证 schema 与同源 controller SHA 后才加入显式 manifest allowlist；`verify_public` 再验证 name/len/SHA、schema、phase 与自己的 SHA。nested、改名到 generic JSON、未列文件均拒绝。为防止改名的 kind 被重复 key/NaN 混淆，本版本同时将 generic JSON verifier 收紧为原 `read_json/strict_json`：有限合法 JSON、无重复 key，默认上限 4 MiB。旧 `public_write` 已产生这种格式；此行为变化会拒绝过去仅按 bytes/hash 被接纳的 malformed/opaque `.json`，是明确的新 verifier 合约，未假称旧原件已重新通过。

## 先停止风险与 owned cleanup，再执行新增 I/O

Health wrapper 只把首个 deadline D2 snapshot 留在内存，并且原 health callback 只调用一次。原 D1 的同步写入/fsync 行为仍存在；本修改不把旧 health 路径宣称为无 I/O 或非阻塞。D2 捕获失败只标 UNAVAILABLE，既有 primary 与 D1 origin 保持。

只有显式启用时，observer 才委托冻结 workload SOURCE 的 `owned_run`，且每次只调用一次，不增加 signal、reap、watchdog 或 retry。正常返回必须同时带 `leader_reaped=True`、`stdout_stderr_complete=True`；信任依据是该固定 SOURCE 的 owned runner 在返回前验证进程组为空、finally 关闭流的源码合约。pending counter 归零且全部观察结果可信才给内部 typed ledger 通过。throw、证明缺失或 tracking 故障使 sticky cleanup_unproven；普通 tracking 错误不覆盖 delegate 原结果，取消不启动新风险，并在没有既有 primary 时传播。外部 JSON 中的“cleanup=true”不是授权。

新增 D2 文件 I/O 只在所有 case 与四流 escrow 的 owned 调用完成后的 global evidence tail 执行；barrier 不成立则只返回 CLEANUP_UNPROVEN / UNAVAILABLE，不尝试导出。没有新增 cleanup 或 case 超时预算。`fsync` 不是可抢占系统调用；该 tail 位于已有 job timeout 内，但本 CODE 不证明 fsync 的完成时间，也不证明目录崩溃恢复 durability。可选导出失败不会更改原 case primary/status，也不会允许 P 在 B 非 PASS 后运行；不吞 mandatory manifest/public verification 的 fail-closed 结果。

## 出版原子性与原 cleanup32 共用计费

检查 private/public 为当前 UID 的真实私有目录，先验证 capsule 大小与共享 cleanup headroom。以 0600、O_EXCL、O_NOFOLLOW、O_CLOEXEC 创建私有 stage，写完 flush/fsync/close 后才用 no-overwrite hard link 发布。不存在覆盖、rename 或跨 FS copy fallback；stage/open/fsync/close/link 失败不发布。已有首 public 文件不重写；半成 stage 留作原始失败证据，不尝试第二次写。

cleanup32 的同一 meter 计旧 D1、现有 escrow cleanup 和固定 D2 public/stage slots；出版前另预留 `2 * capsule_bytes`，即使 hard link 后私有 alias 删除失败也按两条路径保守重复收费。没有新 byte reserve。为保留旧 D1 停止风险前的有限 I/O，D2 slot 枚举仅在内部 quiescent-export seal 有效的 tail 中加入 meter，不给旧 health 每次新增 16 次 lstat。D2 只能由这个 tail 合法产生；未知名、类型/权限/缺失错误不被物理 cap 或 companion 吞掉。

原 case32MiB、normal64MiB、escrow96MiB、cleanup32MiB、总192MiB、额外 host free gate、3 scans / 50ms、case56+2+2、escrow20+2+2、900s fresh gate 与业务 argv 均未增加。四个 closed-stream 的内容、顺序和加密协议不改。导出错误或少了一份 companion 不是“业务未开始/资金无损”的证明。

## 待另授的最小 PURE 计划

新 source 冻结后拟运行一次 CPU2、外层 10s、单解释器 -I -S guarded batch，三个模块共 **76 个声明/预计运行方法**：新 export29、原 D2/interface24、D1 diagnostics23；均直接继承 unittest.TestCase，无测试类继承扩增。旧 D2 与 D1 回归针对新增 wrapper/meter/verifier 接口，原五模块 120 条不重跑。本轮全部 NOT_RUN。

源码闭包仅 controller 与三个 tests（4 个文件，151502 B）；固定 runner 单列，不物化 UTA、业务源码、escrow helper、workflow、cold child。新 0700 private 下仅 KB 合成文件与 fake ownership/stubs；真实 child=0，SQL/UTA import、process/thread 启动、mount/native exec、网络、信号与 crypto 能力均拒绝并记录。Guard 允许 mock 所需被动标准库 import，沿用独立审过的 GUARD_CODE，不启用 six-child 许可；这是已审可信测试的能力限制，不是 hostile Python sandbox。

拟命令为 `/usr/bin/prlimit --fsize=51200:51200 /usr/bin/timeout --signal=KILL 10s /usr/bin/taskset -c 2 python3 -I -S RUNNER SOURCE PRIVATE IDENTITY`。执行前独立核固定 commit/tree 与四文件 SHA/len、runner SHA、干净 source 和新目录；0600/O_EXCL 预开首次 stdout/stderr，合计不超过100KiB，保留实际 binary/runtime、monotonic、guard计数、exit 与首失败，不自动重试。这里是可审查计划，**尚无本 source 的执行许可或运行结果**。
