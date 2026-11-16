# 持久命令、单主机分片进程与历史决策审计：进行中

本轮以 `ad3f5b894f96ed6857a061b71290047ae1d4d0e7`（PR #6）为基线，工程包版本 `0.4.0a1`，交付 [Draft PR #9](https://github.com/PureGamma-Harness/uta-unified-account/pull/9)。当前为 Draft 集成评审，**生产 NO-GO**。所有账户、借款、行情、对手深度及密钥样本均为合成数据；金融、模型、SRE 与真实资金审批均未完成。各工作组实际提交保留在 Git 历史，本文不充当签字。

## 交付范围与明确拒绝

| 接入路径 | 本轮可运行范围 | 未支持操作及行为 |
| --- | --- | --- |
| managed v2 | 合成 USD Cross 线性限价、累计 reduce-only、撤单、已存在债务的同币还款、原命令查询 | 市价、条件触发、改单、多腿、模式转换、开户、存款、新借款、现货订单、跨片划转/对手撮合未接线，明确拒绝；不降级到 v1 同步金融写入 |
| managed 后台 | 真实片内双侧撮合、结算、风险监督、持久部分清算、无流动性保留风险、worker 重启 | 无流动性不生成成交；保险基金、ADL、跨片原子结算与外部托管仍未实现 |
| 离线初始化/接管 | 显式建立或接管既有布局，保持账户分片、原账本和挂单，封存后保持暂停 | 不重分片，不自动恢复缺失财务状态；真实经典源增量流、托管资金证明和源端失效未由本地接管证明 |
| 原参考/单库路径 | 保留此前受测现货、借贷、多币抵押和经典导入能力 | 不因 managed 功能存在而声称这些路径均已具有同等持久接入、鉴权或 fencing 能力 |
| PM / 后续产品 | 精确参考、研究回放保留 | 生产 PM、Isolated、真实 USDT/USDC、多结算、交割、反向、期权仍禁止启用 |

同库 inbox 返回 `202 / ack=durably_queued / PENDING`，证明意图经本地 WAL/FULL 提交，不证明剩余保证金检查或订单接纳。writer 将金融效果、预占和终态回执放在同一实际事务；仅 `SUCCEEDED` 中对应业务回执表示该命令已完成。技术异常先查询原 ID，再有界重试或 QUARANTINED，不冒充业务拒绝。具体协议见 [持久命令](durable-commands.md)、[v2 API](durable-api.md)。

每片使用真正独立 spawn PID，租约绑定 authority、owner、generation、PID、单调时钟和 boot ID；已登记孤儿还以出生身份与 pidfd 核验。本机协调锁和全局行情屏障覆盖实际金融 COMMIT 与后台撮合。不存在跨机复制、leader 共识或 AZ 故障保证，见 [进程运行](durable-process.md) 与 [写入门禁](writer-fencing.md)。

HMAC profile 默认要求本机原生 TLS ≥1.2。请求签名覆盖 tenant、持久 audience、key、时间、nonce、原方法、原 target 与原正文摘要。nonce 先独立持久提交，再做角色授权和业务入队；其提交不是金融接受。永久撤销、轮换、wallclock highwater 与认证库不可用行为见 [签名契约](signed-api.md)。认证库原地旧备份/整机克隆缺乏外部反回滚保证，不能声称全局防重放。

新 managed authority 默认要求 schema3 决策审计；旧 schema2 不自动伪造历史。成功线性接纳与确认成交关联完整历史行情、政策、原始前后状态、代码和运行时指纹。回放只在当前代码及已加载金融实现与当时 artifact 严格匹配时计算，否则要求匹配的 Git/wheel；不执行数据库中的代码。拒绝决策、现货和新借款尚未全部接入该审计范围，见 [历史决策](decision-audit.md)。

## 独立发现与当前验收状态

1. 独立运行真实 `ad3f5b8` 历史源码，发现仅靠当前 Python authorizer 的 lease 检查无法阻止历史二进制继续写入。已加入持久 SQL guard/UDF 格式门禁，并以隔离旧源码进程执行红绿验证；浅克隆 CI 使用带来源摘要与许可证的固定旧源码归档，不替换为当前代码或跳过。
2. 实际 SIGSTOP owner 持 shared gate 时曾阻塞 publication。监督器现在在租约过期后清理其已核验的自有进程，且 exclusive gate 等待有界。实际 supervisor SIGKILL 与已登记停止子进程的组合故障另有 pidfd 恢复测试。
3. 独立审查发现控制事务 DDL 授权过宽，存在金融投影一致性风险；`62f4336` 将 DDL 限制为官方精确 schema，26 项专项与 38 项独立原故障回归通过。[新增独立权限边界复验](fence-control-validation.md)的同一测试在旧源码产生 26 个失败子断言，修复后 8 项在 Python 3.10/3.12 均通过；原失败证据保留。

固定 `6a61c44` 在单独不可变工作树完成双 Python 全量预检，各 **793 项通过**，零失败、错误和跳过：[Python 3.12 原始输出](../evidence/runs/durable-preflight/python312-6a61c44/summary.json)（96.20 秒）及 [Python 3.10 原始输出](../evidence/runs/durable-preflight/python310-6a61c44/summary.json)（98.99 秒）。最终候选尚未冻结；该结果不能改写为后续新增代码已验，也不关闭独立审查已找到的阻断项。原记录器只重定向 Python 层输出，部分实际 spawn stderr 仍输出到调用端；新记录器改用 OS 文件描述符重定向并校验源码前后一致，最终复验使用新记录器，不篡改旧日志补齐。实现组已有针对性测试，独立组覆盖实际 COMMIT 失败、磁盘满、响应丢失、旧进程、部分 publication、同账户 FIFO、poison command、还款和四侧对账，详见 [独立协议验证](durable-validation.md)、[故障验证](durable-faults.md)。

另一次独立审查发现审计只核 guard 名称、未核实际 SQL。`f8d96e8` 共享安装/验证的完整定义，逐项核对 SQL、所属表和 inventory；读档、写决策及行情引用均失败关闭。独立 12 项测试在 Python 3.10/3.12 通过，保留原弱化 guard 红态，见 [独立审计故障报告](decision-audit-faults.md)。签名接口另有 [独立 HMAC/TLS 验证](hmac-validation.md)，9 项测试使用独立客户端 MAC 和真实证书验证。

真实 managed 清算用实际盘口完成 90 开仓、45 部分清算、无深度继续持有 45、kill 后新 PID 接管、再成交 45，终态现金 93.16 USD。schema2 与 required schema3 均逐笔核对；当前价格变化后按历史市场重放三个 victim fill，现金 1000→996.4→544.78→93.16，仓位 0→90→45→0。它是功能/恢复证据，不是容量或灾难恢复验收。

## 实际 24 小时任务与容量边界

用户要求的连续工程窗口始于 2026-11-16 21:02:38 UTC。实际正式同权威长稳于 **2026-11-16 21:36:13.820942 UTC** 启动，请求 86400 秒，原截止为 **2026-11-17 21:36:13.820942 UTC**。不得缩短时长、重置库、拼接不同任务时间或以工具运行时间替代金融状态持续运行。

正式生产者固定在 `88755a9f2ba3bb672ca5d354b3037796f00c6611`，只读观察器固定在 `f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e`；两者有独立可达 experiment 分支。该生产者是本轮早期单库运行模块，**不包含新 managed 进程、schema3 或 HMAC**。它只验证同一固定 authority、固定账户上的低频借贷、真实撮合、部分成交/撤单、重开对账和日志归档；不能用它替代本候选长稳。

负载为 0.25 roundtrip/s，每个正常 roundtrip 两笔真实双腿撮合。独立观察器每 60 秒核对 source、原始起点/截止、实际 PID 出生身份、心跳及只读金融事实。所有长稳和生产 flags 维持 false，直至实际终态、足够 active 秒数、全部计划完成、日志摘要与最终全量对账。初始预检因结果未知后的执行顺序缺陷被停止，保留其失败与 472 秒记录，不并入正式时长。[首小时只读观察](../benchmarks/results/20261116-soak-hour1/README.md)保留实际 PID、起点/截止、成交与独立核对结果，所有正式关卡仍 false。启动和独立观察证据分别见 [正式启动](../benchmarks/results/20261116-soak-formal-start/README.md)、[观察器启动](../benchmarks/results/20261116-soak-observer-start/README.md)；运行与恢复见 [长稳手册](soak.md)。

本轮尚无新 durable 接纳吞吐报告。G3/G4 的 10,000/s×1800s、G5 混合热点/突发长稳及 G6 复制/RPO/RTO 均未通过；不能用 nonce、入队 ACK、worker 尝试、快速拒绝或不同 SQLite 库总量替代持久接纳/唯一清算成交。

## 部署与回滚约束

从冻结 Git/wheel 构建，使用专用用户和私有目录；先执行合成链路、身份/账本/信用/队列核验。只在明确初始化或接管路径启用 managed，保持全局暂停，发布同一真实新鲜 snapshot 至全部分片并核验后，才显式激活。多分片 HTTP 控制仍返回不支持，受控本地操作使用 router 控制协议。

停止时先关闭入口并排空已进入的 HTTP handler，再停止 writer；持久 PENDING 留待原 ID 查询和新 owner 恢复。未知结果先查询，禁止生成新业务 ID 重复作用。租约或 guard 不完整、部分接管、缺片、行情 publication 不完整均保持暂停，不重建财务历史。

managed SQL guards 与 schema3 是格式/能力边界，**禁止原地降级到不认识它们的旧二进制**，也不提供在线 disable fence。修复版本前滚、匹配 artifact 回放是优先恢复路径。需要恢复时保留全部 control、分片、inbox、审计、认证 nonce/key 状态与确切 commit 水位；旧备份遗漏的新成交不能通过删库或改版本抹去。认证与金融恢复必须分别核对，不能把重新生成 audience 当作已完成财务恢复。具体离线升级/恢复须按相应运行手册执行；本机备份不能宣称 AZ RPO=0。

## 工程团队与审查限制

本轮按任务滚动使用持久执行、租约/存储、独立进程/行情、API/签名、性能/观察、独立金融、故障注入、独立边界审查共八个 agent 工作流，root 负责集成。运行环境最多同时 7 个 agent（含 root），不虚称同时运行更多进程或工程人员。交叉审查各有独立文件和 commit，生产签核仍待真实负责人。

已尝试使用 [Codex Security diff skill](skill://Plugin_1e648473be9c8191a91ac3947151af55/security-diff-scan/SKILL.md)。其要求“Run the security_diff_scan preflight from ../../references/config-preflight.md before reviewing files or creating a goal.”当前相应 reference 与 preflight/scan 工具不可用，因此该可选扫描未开始、未通过。独立人工代码审查与实际回归继续执行，其覆盖不冒称为该扫描结果。
