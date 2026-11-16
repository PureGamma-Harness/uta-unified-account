# 独立只读稳定性观察器

`tools/soak_monitor.py` 不启动、恢复或停止生产者，只调用固定源码的 `run_soak.py status`，并用 SQLite `mode=ro`、`query_only=ON` 读取同一 authority 的一致快照。生产者源码、金融数据库、原始 start/deadline 和历史事件不作修改。观察器独立提交、独立进程、独立输出目录；它不是新的交易功能验收。

生产者真实固定 SHA 为 `88755a9f2ba3bb672ca5d354b3037796f00c6611`，已非 force 推到可检出的远端分支：

<https://github.com/PureGamma-Harness/uta-unified-account/tree/experiment/soak-24h-20261116>

```bash
git fetch origin experiment/soak-24h-20261116
git worktree add --detach /tmp/uta-soak-producer origin/experiment/soak-24h-20261116
```

当前正式 job 位于 `/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9`，生产者位于 `/workspace/uta-soak-source-88755a9`；实际原始开始为 2026-11-16 21:36:13.820942 UTC，原始截止为次日同一时间。不能合并已停止的 69ce43b 预检时长，也不能将运行中观察写成已完成。

## 观察规则

- 每次验证生产者完整 HEAD、干净的已跟踪工作树、原始 source_sha256，以及原始 job.json 摘要和 DB inode。`git --no-optional-locks status` 避免读取状态时刷新生产者 index。job.json 的实际 start、配置 duration、deadline、session 开始及单调 active 时长相互核对，不重写任何时间。
- 独立读取 `/proc/<pid>/stat` 的出生标识及状态。PID 出生不符或 Z/X/x 均不计 alive；这修正旧生产者仅查 `/proc` 身份而将僵尸当存活的诊断边界。暂停后的旧僵尸没有计算能力。
- 运行者消失、PID 复用、心跳过期、原始到达缺口、overload 或记录过 unknown 时产生观察告警；保留真实来源，不自动改生产者状态或发送金融命令。
- 自有数据库快照分别统计 done、queued、active、pending 及金融记录。任何 in-flight round 都可能暂时增加订单、仓位、债务，故 golden 差异标为 `inflight_indeterminate`，不自动报财务错误。只有无在途义务的快照才标 `quiescent_matches` 或待复查。
- 终态必须真实达到至少 86,400 秒墙钟和实际 active、单 session、全部计划 done、无在途/未知/缺口、golden 一致、有覆盖最终订单/match/fill 计数的独立 replay 记录，且重新读取所有 gzip 验证 SHA256、条数、连续序列和最终 durable cursor。满足这些也只标 `eligible_for_independent_final_review`；生产、容量和 24 小时批准字段永远 false。

最后 full-verify 记录与当前计数相等不能排除其后同计数内容被篡改，因此观察器不替代最终独立金融 replay、源数据检查和人工验收。它不会把旧 full-verify 或生产者自报通过直接升级为最终批准。

## 单次与周期观察

```bash
python tools/soak_monitor.py --directory /workspace/uta-soak-runs/formal-20261116T213613Z-88755a9
python tools/soak_monitor.py --directory /workspace/uta-soak-runs/formal-20261116T213613Z-88755a9 --watch --interval 60 --duration 86400 --output /workspace/uta-soak-runs/formal-20261116T213613Z-88755a9/observer-<唯一名称>
```

默认从 job 的 launch.json 找到固定生产者；手动启动没有 launch.json 时，用 `--producer-source <固定SHA工作树>` 指定。每次状态调用有 30 秒超时，设置 PYTHONDONTWRITEBYTECODE，不改生产者源码的字节码缓存。读取失败也保留带实际 UTC 的 observer_error 快照，不能用上次健康结果冒充新观察。

watch 每 60 秒保存独立 observation、SHA256 manifest 和 latest，每跨一个真实生产者小时保存 hour 观察。24 小时预计约 1,441 次、通常十几 MiB；硬上限默认 64 MiB、18,000 次观察，interval 最小 10 秒。达到生产者最终待审条件后可以提前结束观察进程，并准确记录观察自身的实际时长；不会改变生产者时长。所有文件私有，旧观察目录禁止覆盖。需要重启观察器时使用新目录，历史目录保留。

为避免生产者递归统计目录大小时遇到消失的临时文件，临时写入放在 job 外、同一文件系统的私有 staging 目录，再 fsync 并原子 rename 到 job/observer 的稳定文件名。观察目录内文件只新增或原子替换，不删除；观察进程退出时仅清理外部 staging。输出不允许为 job 根目录、金融 DB 路径或生产者日志目录。正常停止用 observer 目录内的 STOP 或发送 SIGTERM；这不会写生产者根目录的 STOP，也不会停止交易作业。

脱离工具回合运行时，用 `subprocess.Popen(..., start_new_session=True, stdin=DEVNULL, stdout=<observer stdout>, stderr=<observer stderr>)`；保存观察器 SHA、PID、完整命令、UTC 起止及来源 job 摘要。每小时复查最新 observation 与真实 producer heartbeat，不把静态阶段快照当实时监控。长日志和数据库留本地私有目录，Git 只提交代码、自检、启动及阶段证据。

部署只需要标准库 Python 和固定 producer checkout，无 DB 迁移。回滚或更新观察器只停止它自己的进程、另建观察目录，生产者继续运行；禁止为了修监控重启正式生产者或修改其历史开始时间。观察器与长跑共享主机，属于协同开发流量，不是隔离的容量测试。
