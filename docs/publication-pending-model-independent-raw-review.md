# Publication pending 首次运行独立 RAW 复核

**ACCEPT_FIRST_BOUNDED_MODEL_RAW_RECORD_WITH_EXPLICIT_LIMITS**。复核固定模型源码
`2ff960eb7ec5b5ad19e366448237a010254c7f47` 与独立 CODE 审查
`94b1c9da352c9fbeedd99734f0db01162c071ffc`。本次只读取 Git、源码、封存原件与
JSON；没有导入或执行模型，没有调用 explore/replay/run，也没有 SQL、proc、worker
或重跑。详细数据见 [独立 RAW 记录](../evidence/reviews/publication-pending-first-raw/independent-raw-review.json)。

## 原件与执行证据

9 份原件共 68621 bytes，seal 1691 bytes，SHA-256
`50078c83e78be80186ea14991f4979679f8a34922fb07e45006d6052a7fd9ff0`。
逐件大小、SHA、普通文件类型和 0400 权限均匹配，目录 0500；未修改原件。
完整 stdout 46945 bytes，SHA-256
`fc393727703b954f5544cf5132eecd3a528d0131bbd5edc475c34a475f5fcdd3`，
是一个完整、无重复 key、带末尾换行的 ASCII JSON；stderr 为 0 bytes。

使用模型原件、Git blob 与物理源码逐字节相同：11472 bytes，SHA-256
`8d6ead3a0f9c9d58c52d6659db3fac090bea9b9f9b5e57d6430eefef247f93fb`。
使用 wrapper 与计划内文本、实际命令参数逐字节相同。实际命令选择的解释器文件
与 preflight 的 30894944 bytes / SHA-256
`fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7`
匹配；这依赖 preflight 至启动间运行环境受信，不是执行中自证明或远程证明。

| 证据层 | 实际记录 | 含义 |
| --- | --- | --- |
| 外部工具完成记录 | chunk 914815，exit 0，无 session | 封存 root witness 内的工具结果 |
| root 外部退出见证 | exit 0 | 独立于 prefix 的退出字段 |
| prefix start/end | actual_process_exit 均为 null | prefix 不假装知道最终进程退出 |
| prefix end | model_returned=true，source 前后相同 | wrapper 正常推进到结束记录 |
| prefix elapsed | 107657743 ns | 模型 wrapper 的观察区间 |
| 工具 wall 元数据 | 0.000025701 seconds | 不等于 prefix 区间，不用于性能成绩 |

本审查读取封存的 root 工具结果，没有向工具提供方独立证明所有历史调用的唯一性。
记录显示未自动重试，本审查也未重试。源码/命令为 direct exec 和同进程 runpy；
未创建模型 Popen child，本审查没有通过 proc 观测进程树。
stdout/stderr 由普通文件重定向接收，wrapper 调用 flush/fsync 后才写结束记录；
不存在 pipe EOF、子进程 wait/reap 字段可供补造。调用成功不证明物理介质持久性。

命令包含 -I/-S/-B 和单个预选 CPU；wrapper 对运行进程设置 AS 512MiB、CPU 60s、
单文件 FSIZE 1MiB。namespace 计划上限 8MiB，实际含 seal 为 70312 bytes。
这些是资源限制与观察结果，不是峰值内存测量、目录总量硬隔离或硬 wall watchdog。

## 模型输出及逐条 trace 核对

正常 variant 报告 complete=true、854 个发现状态、3339 条遍历边、violations=[]。
七项 coverage 均大于零，且属于状态计数，不是所有崩溃位置的覆盖证明。
八个负例均报告其指定 tag、replayed=true；其 complete=false 表示已找到反例，
不表示负例搜索穷尽，也不表示 state-limit 超限。

独立数据核对检查了八条 JSON trace 的全部 43 个迁移：固定初始状态、20 个状态
字段的闭合 key/类型/域、动作前置条件、完整字段变化及指定坏终点均匹配。
没有执行目标 replay；replayed=true 是绑定到本次源码和退出记录的实际模型报告。
本次有限 trace 数据检查不充当独立生产参考实现，也未重新枚举 baseline 图。

| 负例 | trace 边数 | 实际坏终点 |
| --- | ---: | --- |
| exception_without_freeze | 8 | fatal 已观察但 pending 保留 |
| late_publication_revives_pause | 7 | operator_halt 下 pending 被复活 |
| late_activation_reopens_gate | 9 | captured revision 0 / current 1，仍开闸 |
| partial_fanout_visible | 4 | 第二片 receipt 仍为 0，market 已可见 |
| paused_poll_charges_attempt | 2 | PENDING 且 pause 时 attempts 变为 1 |
| duplicate_admission_reserves_twice | 2 | 同一合成 CID 已成功却 reservations 变为 2 |
| activation_ignores_stale_quote | 9 | 最后 activation witness 的 fresh=false |
| restart_forgets_pending | 2 | publication 后 restart 丢失 pending |

特别保留原始顺序：late_publication 的实际最短反例先 halt，再 begin publication，
captured/current revision 都是 1。它证明 operator-halt 分支失效；不能按负例名称
把它改称 captured0/current1 的旧 publication 时序竞态。late_activation 则确有
capture0、halt 推进 current1、随后开闸的实际 trace。模型仅原子化假定 stop 写成功；
stop-record 写失败未建模，不能由本结果推导真实系统中的安全恢复结论。

## 公开导出建议与剩余门槛

建议 root 完成 SAFE 首次数据交付后，允许**仅精确导出上述 46945-byte stdout**，
并另作导出字节 delta 复核。已检查完整 JSON 的闭合 key、类型和常量：内容是纯
合成控制状态、固定动作/tag、0/1 模型版本/逻辑片、计数及布尔值；无真实账户、
身份、时钟或生产 shard/CID。不能随之导出私有 wrapper、prefix、root witness、
实际 CPU 选择、绝对路径或其他环境数据。本审查尚未复制或公开完整 stdout。

没有 runtime refinement、liveness/fairness、stop 写失败、物理 fsync/复制或真实
lease-age 证明，也没有金融金额、撮合、账本、清算、HA、吞吐或生产批准。
本提交只新增两份 SAFE review；revert 即可撤回，不改变模型或封存原件。
