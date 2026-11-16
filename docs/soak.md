# 可恢复的 24 小时合成稳定性作业

`benchmarks/run_soak.py` 长期使用同一个 `authority.sqlite3` 和固定三个账户，调用真实 ExchangeService、Matcher 与 CreditService。财务数据库不会轮换、清空或以新测试库替代。全部资金、行情和交易对手是明确合成数据；没有托管、外部交易所或真实资金连接。

这是单主机、单权威、cache0、共享开发主机上的低频稳定性作业，不是万笔容量验收，不覆盖随后提交的 managed inbox、process fence 或其他新模块。每个候选必须有独立 job 目录及不可变源码 SHA；旧 job 的 24 小时结果不得归给新候选。

## 负载与资源预算

默认真实运行 86,400 秒、0.25 roundtrip/s，计划 21,600 round。计划到达使用原始绝对时间，队列和执行中合计最多 32 项。队列满仍将该次到达及 overload 持久保存，不靠延迟下一次计划到达隐藏积压。每轮先开仓后用真实对手方反向撮合归零，两个方向都是实际撮合成交和两侧账务提交，没有调用 apply_fill 或按标记价生成成交。

| round | 开仓量 | 真实 match | fill 腿 | 订单 | 额外行为 |
|---|---:|---:|---:|---:|---|
| sequence % 10 = 0 | 买 .02，仅卖 .01 | 2 | 4 | 4 | 首笔真实部分成交后撤销买单余量，再只减仓平 .01；1 个部分撤单 |
| sequence % 10 = 5 | .02 | 2 | 4 | 6 | 先挂不交叉 99 买/101 卖，真实 match 返回 0，确认两侧撤单，再正常往返 |
| 其余 | .02 | 2 | 4 | 4 | 两侧只减仓平仓 |

因此完整默认作业的 golden 为 43,200 unique match、86,400 fill 腿、90,720 orders、6,480 cancelled orders（其中 2,160 个有部分成交）。每 60 round，第三个独立账户以同一组原始 ID 借入 .01 BTC、确认外部合成利息事件 .00000001 BTC、还清本金与利息；默认 360 个完整借贷周期，另有一次合成池注资。利率调度不是本工具声称实现的生产计息规则。

USD 每账户初始 1,000,000；借贷账户另有 1 BTC 利息缓冲，池有 1 BTC 授权为合成资金。每秒实际向生产 publish_market 路径提交独立递增版本、实际 UTC 观察时间和 .01 步长的合成价格 tick；最长允许行情年龄仍为 5 秒。断流不改写旧观察时间，不用未来时间抵消停机，新增风险遵循原服务的过期行情拒绝。

目标数据量在 GiB 以下，硬上限为财务 DB/WAL/SHM 合计 4 GiB、整个 job 6 GiB、剩余磁盘至少 1 GiB。触限立即停止新到达，保留在途义务和失败状态。资源上限不是事后删除旧账的许可。默认每 5 秒持久 heartbeat，每 60 秒导出压缩日志，每段最多 1,000 条 evidence；每 60 秒只读轻检，每 900 秒完整只读重新连接、账本及独立 reconciliation。固定数量线程：生成器主线程、一个真实 settlement worker、一个 live-feed worker。共享主机上其他工程及 CI 流量明确记录，不声称专用硬件隔离。

## 持久状态与恢复语义

计划到达、queued/active/pending/done/overload、各动作 checkpoint、不可修改 evidence、session 的原始开始/heartbeat/active 纳秒和导出范围都在同一权威 DB。动作与工具 checkpoint 是两个提交；工具没有声称这两者跨调用原子。每个财务命令有原始、确定性的业务 ID：

- 订单恢复重放原 account/order ID，不换 ID；完成 checkpoint 还须能追溯不可修改的确认记录和真实订单经济条款。
- 撮合恢复先查原两侧 order ID 关联的真实 trade_id 及确认数量；只有数量等于本轮义务才推进。订单存在、已接纳或排队不代表成交，未成交余量保留。
- 部分成交撤单确认后才推进只减仓指令；重复执行不会反向开仓。
- borrow、interest、repay 使用原命令 ID 查询/重放，已计利息不得重新计一次。
- 压缩导出先持久计划该段 first/last，再写文件及 manifest，最后推进 cursor。中断后沿原范围恢复，不能因为新 evidence 到达扩大已计划段造成重叠。

重新启动前校验同一 DB inode、原始 job 配置、完整源 SHA/内容摘要、schema 摘要及 quick_check。先做只读检查，拒绝通过构造器重建损坏 guard 来掩盖问题。启动对金融记录作只读独立 replay；每次完整验证的时长独立记录，不能把验证时间从端到端到达延迟中扣除。长跑期间没有初始化新账户或重复补充资金。

作业持有独占 OS flock，第二个 job writer 不能同时运行。状态命令通过 PID 与 `/proc` 进程开始标识检查存活，识别 PID 复用；僵死或消失的运行者报告 pending，不把旧 progress.json 当进程仍在运行。此锁仅保护本地 soak 作业，不构成交易平台 HA fencing 验收。

停止与恢复保留原 `started_ns`、原 deadline 和所有业务 ID。session active 时长来自实际单调时钟 checkpoint，进程停机不计入 active；恢复期间错过的计划到达标为 missed_downtime。单独保留每个运行窗口，未完成保持 paused/pending/failed。24 小时稳定性通过还要求单一完整 session、至少 86,400 秒实际 active、全部计划 round 完成、golden 与真实财务一致、最终日志审计通过。重启恢复正确性可通过测试，但中断作业不会被包装成连续 24 小时通过。

## 启动、状态、停止与恢复

先对工具做短时自检并提交；实际长跑使用该真实提交的独立 worktree，整个作业不修改该 worktree。

```bash
python -m unittest discover -s tests -p 'test_soak.py' -v
python benchmarks/run_soak.py start --directory /workspace/uta-soak-runs/<唯一job> --duration 86400 --rate .25
python benchmarks/run_soak.py status --directory /workspace/uta-soak-runs/<唯一job>
python benchmarks/run_soak.py stop --directory /workspace/uta-soak-runs/<唯一job>
python benchmarks/run_soak.py resume --directory /workspace/uta-soak-runs/<同一job>
```

正式启动用 `subprocess.Popen(..., start_new_session=True, stdin=DEVNULL, stdout=<private file>, stderr=<private file>)` 脱离调用工具进程，保存实际 PID、源码路径、完整命令及启动 UTC。后台作业依赖该计算环境持续存活，不能保证宿主环境 24 小时不被回收。环境中断时通过 status 识别 pending，必须查原 job 恢复；不得改 started_at 或手工生成未来成功结果。

stop 写入同一私有目录的 STOP 请求；生成器停止，已接纳工作排空，行情继续到排空结束。SIGTERM/SIGINT 同样请求有记录的停止，不直接删除任何金融记录。结果未知先按原业务 ID 查询，无法确认的步骤保留 pending。修复脚本或引入新运行时后，应另启新的 candidate job；原 job 保持它实际运行过的源版本。

## 监控、原始证据与验收

job.json 保存不可变原始时间、负载、源摘要、环境及财务 DB 身份；progress.json 是便于查看的原子替换读模型，权威以 DB 和动态 status 查询为准。heartbeat 记录各到达状态、排队、市场年龄、真实订单/match/fill/credit 数、磁盘和 RSS；每 round 保存计划/执行/完成及实际端到端延迟，汇总 P50/P95/P99/P99.9。no-liquidity、partial、cancel、round 尝试及实际确认成交数分别记录。

原始 evidence 在 DB 中追加且禁止修改/删除，按范围导出 gzip，manifest 保存范围、条数、SHA256 和字节数。文件 fsync 与元数据原子替换不能单独证明整个主机或介质断电模型下 RPO=0；没有跨可用区复制。最终归档必须重读全部段、校验 hash 及连续序列覆盖当前 durable cursor。DB、长日志保留在私有 job 目录，不提交 Git；公开提交源码、自检证据、启动记录和适量合成进展摘要。

只有达到实际 24 小时并通过所有检查才能改变 stability_target_passed；运行中、暂停、未知、中断、磁盘不足都保持 false。production_approved 与 capacity_10000_per_s_passed 永远 false。结束报告应包含真实运行区间、active/downtime、全部计划/完成/过载/错误/剩余数量、撮合/两侧账务与仓位核对、资源峰值和 manifest。此作业不批准真实资金。

回滚仅停止该合成作业并保留数据库、原始事件和未完成义务；修复版另建 candidate 或在同一不可变源码下按原 ID 恢复。不得删除旧 DB 后创建同名目录继续宣称原运行时间。

## 首个预检候选与故障后队列屏障

首个候选 69ce43b 于 2026-11-16 21:28:34.484473 UTC 实际启动，后续自审发现未知结果后的队列因果屏障缺口：生成器虽停止，worker 仍可能执行后续 round，消费前一轮尚未完成的盘口。真实 live 作业当时未遇到此错误，但不能据此忽略恢复契约。新增回归在第一轮只提交买单后丢结果、同时已有两轮排队，验证后两轮保持 durable queued 且未创建任何订单，随后按原 ID 逐轮恢复得到恰好六笔真实 match。

修复版首个错误后只保留后续义务，不继续金融执行。修复候选使用新的独立 authority、实际 start 与 24 小时 deadline；旧候选 graceful stop 并留下 INTERRUPTED_KNOWN_ISSUE 注记、原 DB、原 start、原 deadline 与历史日志。旧时长不并入新作业，旧源码不被暗中修改，不跨 source resume。首个预检及 known-issue 原始记录见 benchmarks/results/20261116-soak-start。
