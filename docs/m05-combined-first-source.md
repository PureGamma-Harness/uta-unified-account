# M05 fixed combined source：仅合成低量诊断准备

本 CODE 合入独立 OWN `837bd0ac8c43550590d8637000dea18db746d3ff` 和 `d49e85e73f629b44a0a980d5a75d8a83f6530cae`。single-use token/proof 组件 CODE 已独立关闭；a365 原 pending、c524 的原 19 PASS / 1 RED、M01–M04 首 FAIL/UNKNOWN 均保留。

只给 manual dispatch 的 sparse checkout 补一条 `/.github/workflows/independent-m0-once.yml`，满足两个测试模块对两份 YAML 的实际读取。once workflow、controller、escrow、公共 recipient、B/P argv、05 namespace、预算均不改。controller 的 61 个 function/class AST 继续等于固定 FS，仅两 namespace 常量相对 spent04 更新。`combined-source-bindings.json` 绑定 controller、两 workflow、九测试、helper、证书、policy、strict false 模板与执行器 SHA256。模板严格 19 字段，execution_authorized=false，control_commit 零值；next_run_permitted 只在外层 policy，持续 false。

root 已具体授权对本次冻结源码执行一次 combined PURE：CPU2，外层 30 秒，等价两 workflow 的九模块 `unittest discover -p 'test_independent_m0_*.py'`。源码冻结时尚未执行，组件旧结果不作为该树通过证据。测试器只物化必要 16 个文件和 safe metadata，没有 uta、工作负载、完整仓库或私钥。实际 WORKLOAD 仍只能是完整 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` / tree `cee60bc0b5413551030300e065d0dcaac6a7ff55`；控制树 uta 对 6010 的 `4a0d5a989f0d7112454e41bbdb0162ffef34dbe4` 零 diff。

执行器在导入测试前安装父 guard，仅允许 helper 原 CHILD_CODE 的六次精确 `Python -I -S -c`：新 SQLite/UTA 负控、controller/escrow 正控，加旧 escrow/controller contract caller。它保留原 helper 代码，给每个 child 前置硬 guard，禁止其他 process、SQL connect、网络、线程、信号与 ctypes/native execution；原 cold guard 在任何 SQLite/UTA import 和目标源码 exec 前已就位。父亦拒绝 SQLite/UTA import。每个 child 留独立 hard-guard 自检、退出和回收记录；每个 helper 调用及实际正负控 proof/stream 原件保留。测试中 timeout/reap/crypto 等仍为原纯桩，桩所期待的 UNKNOWN 不等于真实 child UNKNOWN。原始首 stdout/stderr 不过滤、不覆盖。任何实际首次 FAIL/ERROR/UNKNOWN 或数量/guard 不闭合，停止且不得同源重跑求绿。

这次授权不含 actual M05、marker、ref、push、CI、SQL/业务/worker、真实 OpenSSL 或网络。没有部署服务或修改 schema；回滚仅回退本 CODE/docs 并保全部首证据。后续部署仍须完整树独立审、root 最后具体 M/push 授权、fresh host/boot/资源、strict19 marker 与 sole-parent/sole-added-path 校验。05 首 push 将消耗登记，任何未知响应只读核对，不重放或复建 ref。01–04 仍 spent。

未来候选也仅为合成低量 20/s × 10 秒、100 accounts、2 shards、B 后 P；不代表 10k/s、HA、生产或真实资金。3scan/50ms、56+2+2≤60、字节/host gates、四流 CMS 与公共证书约束不变；production/capacity/HA 和 next_run flags 全 false。
