# 默认 OFF D2 Draft 候选

本候选以 PR35 的 `delivery/m05-control-package-fix@9b61e5f35dd2196ef2fdddfa03559eca3f1322ec` 为精确 base，仅整合 D2 memory capture、quiescent-tail companion、严格 proof/public verifier、未实现的 kernel-space 接口、测试、设计与安全首测原件。controller 与已审 SOURCE `8594a35827b0e064584113de48fda2490cb1c98e` 逐字节相同：104961 B，SHA256 `67a97e551590ff4f23d1256c79ad5b9ae0259e9973012541cee678ab1842ca93`。本 delivery 树未运行新测试、package/build、guard、GHA 或任何实际 case；旧 source 的通过不转签为 delivery 的新运行。

`D2_COMPANION_EXPORT_ENABLED=False`，capture ContextVar 默认 None，kernel backend 固定 NOT_IMPLEMENTED / NOT_VERIFIED。没有环境变量或 CLI 启用路径。默认 OFF 不代表全部修改无行为变化：generic public JSON verifier 现在始终要求严格有限 JSON、无重复 key、至多4MiB；保留 D2 namespace 且禁止 companion 改名借用 generic route。此收紧明确属于本 PR 的 CODE 合约。D1 producer/schema 九字段、3scan/50ms 的原 predicate 值、host gates、业务 argv、原 case/escrow/cleanup 字节与时间预算保持；四个 closed stream 与 escrow 工具不变。

## 首测证据的准确范围

| 首次 source | 实际 scope | 原件与结论 |
| --- | --- | --- |
| `3040d09b576009893c6630f3c19ef4ad35fd774d` | 5模块/6源码158305B；99 declared +21继承=120；当时 controller 为8778b978… | 首120 PASS/exit0/CPU2/child0；D2内存和NOT_IMPLEMENTED接口及四模块回归，未包含后续持久export |
| `8594a35827b0e064584113de48fda2490cb1c98e` | 3模块/4源码151502B；29export+24D2/interface+23D1=76，无继承扩增；controller67a97e55… | 首76 PASS/exit0/CPU2/child0，独立raw closure PURE_ONLY PASS；7原件19673B，target169015517ns/outer389344436ns |

两次是不同固定 source 的独立首结果，有重叠测试，不能合称一次196条或最终delivery完整suite通过。76闭包中的 controller、三个 tests 与 runner 在本候选中逐字节保留；120那次 controller 不等于最终 controller。全部 first ERROR、guard stub、旧 M05/PR35 原始证据保留，未重跑求绿。`evidence/designs/*` 内冻结阶段的 NOT_RUN 文件是历史原件，最新状态另见各 current-status 与独立 closure。

## 信任和未覆盖的边界

启用后 health wrapper 只新增内存排队，原 health callback 仅调用一次；旧 D1 同步写/fsync 仍存在，不能宣称 health 为无 I/O 或非阻塞。持久 D2 仅在所有被观察 owned 调用结束、typed/sticky cleanup ledger 闭合后的 global tail 导出。Capsule≤4096B，0600/O_EXCL stage、fsync/close 后 no-overwrite hard link，public/stage双alias保守共用原cleanup32，无copy fallback、额外reserve、retry或新watchdog。fsync非可抢占，尚未证明其完成时间或目录崩溃durability。

strict proxy 依赖固定 workload `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` / tree `cee60bc0b5413551030300e065d0dcaac6a7ff55` 的源码闭包。主路径 source_snapshot 验证全部源码；`tools/run_managed_variants.py:591` 在正常返回前强制 owned session 无存活组成员，finally关闭流/selector/pidfd；driver显式继承session，冻结benchmark/spawn调用链不脱离进程组。仅凭 leader_reaped/EOF 两个外部boolean不能授权导出，任一throw/证明缺失/tracking疑点均sticky UNAVAILABLE。该受信继承组合约不证明防逃逸或完整OS sandbox，不允许从 M05 旧JSON倒推 closure。

原协议继续拒绝tmpfs/ramfs。固定192MiB disk-backed FS/project quota仍只是NOT_IMPLEMENTED接口/spec，没有mount/loop/sudo/CAP/quota/noescape或charging canary证据；normal64单卷也不自动满足每case32物理上限。卷内metadata与host backing/kernel RAM等边界在独立设计中说明，不声称全host或全I/O受限，不与旧625 disk-WAL/FULL基线直接同比。

M05 B UNKNOWN / P NOT_RUN及spent05不变；新D2不能补录其attempt/elapsed，也不能证明DB corruption、业务未开始或资金损益。production、10k/s、HA、真实资金、实际GHA/M06、registration、push/dispatch授权均false；下一次pure预算也未授予。

## 打包选择和交付方式

MANIFEST.in 与 pyproject.toml 完全继承 PR35。两条精确 inputs.sha256 literal 保留；本D2新增.sha256为零，现有 docs/tests/tools/evidence扩展规则静态覆盖全部D2及本次Draft元数据。它是 sdist 选择，不是实际归档结果；wheel配置仅列 `uta`，不能声称wheel携带controller/tests/docs/evidence。新delivery sdist/wheel/archive成员验证全部NOT_RUN。

本次只准备普通delivery分支的Draft title/body，base应为 `delivery/m05-control-package-fix`。待root审核精确候选source/tree/diff后，由root另授权普通分支push与Draft PR；本轮未push、开PR或触发GHA。不得使用perf/approved分支。

部署是将默认OFF控制代码供review，不部署业务。未来若要实际synthetic诊断，必须另冻结启用constant与controller SHA、独立storage profile/registration/ref、fresh workspace的准确900s gate和root具体scope；仍为20/s、10s、100account、2shard、CPU1、原B/P argv及全部字节/host门槛。当前不创建06 marker，不使用05，不构成10k/HA/真实资金证据。

回滚候选为新普通CODE commit：把controller恢复到PR35精确base，并同时移除本PR新增两份D2 tests以匹配接口；保留所有first原件、closure和PR35两literal修复，文档记录回滚后的现状。回滚不重写历史source/evidence或修改spent05，也不自动重跑、启动业务或延长旧预算；具体patch仍需审查。
