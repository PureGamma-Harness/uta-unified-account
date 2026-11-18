# 完成前缀取证审计 v1：契约、手算例与源码方案

本提案补齐已经静止的合成任务的**完成轮次前缀**事后核对能力。当前仅有规则、receipt schema、手算标准例与源码方案；SQL、备份、审计、observer、进程操作和实际旧数据写入均为 NOT_RUN。它不会更改原 `producer_audit`、`audit_job`、六小时终态 gate 或旧运行结果。

冻结参考源为 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`。实际 909 已在 4,357 / 5,400 轮、19,443.305304647s 因原 observer 输出预算超过 2GiB 而 paused，完整六小时与 coverage 为 NO_GO；首次终态 `d243f8c5a12b4a0c8c2f593813b621317a774013` 保持不变，并交 `/root/terminal_firstseal_review` 独立审查，作者不自签。该运行未取得成功的 strict cold receipt，已完成前缀的 golden 观察不能补成此 receipt。

## 产品与授权边界

v1 只覆盖原固定三账户、USD/BTC 各 8 位、BTC-PERP、原每轮四单/四 fill/两 match/两 satoshi 还款的合成 workload。只有原状态 paused、`1 <= K < N`、已确认静止、无未完成动作、完整证据归属和日志边界时，才可能得到 `PREFIX_VERIFIED`。N 是**原计划**轮数，K 是原控制器确认为 DONE 的最长连续前缀，不能重新取最有利的子集或把 N 改成 K。

v1 拒绝 failed、running、未知原状态、零轮、非该合成 profile、不同 source/schema、非零利息、不明人工调账、未归属订单/成交及超前业务事件。failed 任务需另版规则说明具体失败性质及未决义务，不在此默认放宽。尚未证明 quiescence 或证据不足时，输出 REFUSED/INCOMPLETE；不为“拿到部分结果”忽略尾部未知风险。

该功能是离线调查工具，没有 UTA 账户写权限、API 交易权限、解锁权限或上线签字权。无论前缀核对结果如何，receipt 的原任务完成、六小时、24小时、金融六小时、容量、完整风险/业务状态重执行与生产批准均保持 false。新 receipt 必须有独立类型和独立输出目录，不写入或替换原 `producer-cold-audit-receipt.json`，不能被旧终态 gate 接受。

## 规则追溯与拒绝契约

| ID | 规则与依据 | 拒绝/缺口 | 计划验证编号 |
| --- | --- | --- | --- |
| PF-01 | 909 `audit_job` 要求 completed 且 listener 停止；`producer_audit` 要求其他 final checks 已过。两函数及原 final gate 保持原样 | 不改 paused 为 completed，不补旧 cold receipt，不调用旧 strict audit 来冒充新模式 | PFT-01 |
| PF-02 | 原 job/environment、baseline、source map、workload spec、代码与参数、运行时、原 SHA 和外部已审 bundle manifest 绑定 | 自算未知 manifest 的 SHA 只校验一致性，不建立来源真实性；任何身份/版本未知则 REFUSED | PFT-02/03 |
| PF-03 | 新政策：静止证据必须覆盖原 driver、listener、全部 shard worker、router/账户写入者与投递者，租约与 fencing 独立核对 | 单个 PID 消失、driver exit 或 lease 过期均不能单独证明全体静止；无法证明则不开 SQL | PFT-04/05 |
| PF-04 | 909 checkpoint 规则要求 DONE 连续；原步骤、fault、CONTROLLER_ENDED、日志 head 与金融 command coverage 关联 | 不得舍弃 ACTIVE K+1、未决 step/fault、重复/缺口或 UNKNOWN 行动；不推进 checkpoint | PFT-06/07 |
| PF-05 | 909 `original_command_coverage` 对每轮六个原命令 ID 核对 checkpoint 与金融 inbox；`_golden` 逐单、fill、match、risk decision、credit 与账本核对 | 每个 ID 唯一、所有已发动作可解释；仅总数相等不足，不读查询端缓存来补确认 | PFT-08/09/10 |
| PF-06 | 909 `verify_logs` 逐段 SHA、序号与 event hash 到 checkpoint head；`_golden` 逐币守恒、分录哈希及全 owner/asset 投影重建 | 缺段/损坏/重复/孤立 posting/不可归属成交/缺币种均 FAIL；不能裁剪到较早好前缀 | PFT-11/12 |
| PF-07 | 新模式独立计算 `R=2(N-K)`，资产与本金负债保留 gross 分量 | 不将 N 改 K 清零欠款，不把借入币和负债无依据净额；利息非零或不明则 v1 拒绝 | PFT-13/14 |
| PF-08 | 独立完整私有 backup/clone 后两次重开核对同一 checkpoint/business/ledger watermark，与原源冻结边界一致 | 三库不具备跨库原子提交；必须先证明全体不再写入并对齐逻辑点，不承诺不具备的原子快照 | PFT-15/16 |
| PF-09 | 原 market/control lane 也需关联源事件，bootstrap 与每轮 feed、halt/activation barrier 有独立归属 | 不能按“无 account_id”忽略未知控制命令；合法初始 market 不是额外业务轮，不能靠总数猜归属 | PFT-17 |
| PF-10 | 新政策采用精确 integer/count、规范正 ASCII decimal birth、类型敏感 JSON 关联、有界流式输出 | bool/float 伪装 count、前导零 birth 别名、无界输出、超限后只保 metadata 均须明确拒绝/未知 | PFT-18/19 |

以上新政策是本系统的取证规则，不声称某交易所公开规则保证其正确。金融规则负责人、独立验证组签字以及真实资金上线批准当前均未完成。

## 分阶段执行方案（本轮均未执行）

1. **授权与来源封存。** root 先审核确切 source、数据集合、硬件、只读策略、资源与总时限，发出一次具体执行 GO。input bundle manifest 的原始字节 digest 由独立审查绑定；只允许原 job/checkpoint/router/shard 数据、原事件日志和验证资料，权限 0700/0600。原 auth/TLS/key/HTTP nonce store 不拷入审计数据集合；完整账务库可能含历史 nonce 或其他敏感列，opaque clone 全部私有，禁止公开或重构为丢列“等价”库。
2. **先证明静止。** 在任何 SQL/备份前，使用已封存 writer inventory、原进程 lifetime、监督器终态与已授权运维的静止证明，确认所有潜在写入者均已覆盖。单独给审计 namespace 挂只读目录只约束审计进程，不能证明外部 writer 已停止。若 fence/lease 的充分事实只能从新 SQL 得知，预检阶段标 UNKNOWN，等待独立审查的隔离证明；不能偷偷提前查库或靠过期时间猜结论。元数据缺失、可用区/远端写入者不可见或旧主恢复可能未排除，输出 REFUSED。已具备隔离前提后的只读数据库阶段再复核持久 fence/lease 与原归属，任何不一致仍拒绝。不得为了获得静止证据发送信号、启动 recovery worker 或创建新 generation。
3. **建立只读物理输入。** 在 kernel 原目录只读约束下，验证完整数据库与 WAL 集合、原 dev/inode、日志清单和内容哈希。非空 WAL 不能用 `immutable=1` 静默忽略；没有可证明的只读一致复制方式时停止。未来 private backup 只写新私有目录，前后原输入 fingerprint 一致；不触发原库 checkpoint、journal mode 修改、schema constructor 或 sidecar 创建。若 SQLite 必须写原 SHM 才能打开，则拒绝并保留原因。
4. **确定唯一边界。** 读取私有 checkpoint 与原结束事件，要求原 controller session=1、boot/source 不变、原状态 paused、DONE 为 1..K 且无 ACTIVE/RECOVERING、无未决 step/fault；校验原 planned_ns、completed_ns、起止时钟的实际值，不制造连续时长。CONTROLLER_ENDED 与原 producer/progress 一致。任何 K+1 的已接纳/在途业务义务或未知命令使整体 prefix receipt INCOMPLETE；不只审前 K 条后忽略其余。
5. **重开与独立逐项核对。** 在新 clone 上采用不调用 UTA engine/constructor 的只读查询器，流式导出带稳定排序与整数单位的完整表集；独立参考器核对所有 owner/asset、债务、订单、risk decision、market/policy/artifact content ID、两侧 fill/match、费用、position 与逐事件分录。按原 checkpoint step 的 payload digest/原 command ID 逐一 join。control lane 的 bootstrap/feed/activation/halt 每条也必须找到原源事件，单列其版本和业务影响。
6. **日志及同水位证明。** 逐 gzip 段检验原 SHA、连续序号和哈希链直达原 checkpoint event head，再从全 journal postings 重建 owner/asset 投影并逐币/逐事件守恒。第一次与第二次只读重开得到相同完整 business digest、ledger head 与 checkpoint head；同时确认源仍未变化。输出每项检查、实际读取量与失败数，不能仅继承 prefix golden=true。
7. **独立输出。** 输出独立 `completed-prefix-forensic-receipt.v1` 与有界摘要。完整表流、clone、未筛选原错误和敏感数据留私有存储；公开仅合成结果及哈希。即使 PREFIX_VERIFIED，`complete_original_job=false` 和全部 qualification=false；旧运行、旧 receipt、旧 NO_GO 不改。

预算须在执行前列明输入字节/预估 clone/空闲下限、峰值 RSS、SQL busy/每阶段与总时限、日志解压量和输出硬上限，超限状态为 INCOMPLETE。原 2GiB 事件证明输出必须受控：默认摘要不输出逐命令全量数组；详细流写入有界私有文件且每段保存 digest。这里只提出接口与要求，没有宣称物理配额或时延上限已经实测。

## 手算标准例：N=3，K=2

这是新合成标准例，**没有实际执行**。原计划三轮、只完成两轮；初始客户各 1,000,000 USD，credit 客户另有 1 BTC，pool 投入 1 BTC，原借款 `2N=6 satoshi`。每轮 Alice 的 +0.02 单仅成交 +0.01 后撤余量，Bob -0.01 对手成交；随后双方以 100 USD/BTC 反向平仓各 0.01，PnL=0；四个 fill 各收 40,000 个 USD 最小单位，最后归还 2 satoshi 本金，利息为零。

K=2 后应有 8 orders、8 fills、4 matches、2 partial cancellations、12 account commands、16 risk decisions、`6+5K=16` ledger events，余额/负债不得把 N 改成 K：剩余本金 `R=2(3-2)=2 satoshi`。每位交易客户累计费用 160,000 USD 最小单位，system fees 为 320,000；没有未完成订单或仓位。

| owner / asset | 期望最小单位 | 解释 |
| --- | ---: | --- |
| customer:managed-soak-alice / USD | 99,999,999,840,000 | 100,000,000,000,000 − 2×80,000 |
| customer:managed-soak-bob / USD | 99,999,999,840,000 | 同上 |
| customer:managed-soak-credit / USD | 100,000,000,000,000 | 不以负债净扣现金 |
| system:fees / USD | 320,000 | 2×160,000 |
| system:custody / USD | −300,000,000,000,000 | 三笔 USD 合成 backing |
| customer:managed-soak-credit / BTC | 100,000,002 | 1 BTC 加剩余借币 |
| system:credit-pool / BTC | 99,999,998 | 1 BTC 减剩余借币 |
| liability:principal:managed-soak-credit / BTC | −2 | 本金负债单列 |
| system:credit-principal-receivable / BTC | 2 | 本金应收单列 |
| system:custody / BTC | −100,000,000 | 客户原 1 BTC backing |
| system:credit-capital / BTC | −100,000,000 | pool 原 1 BTC backing |

USD 五项和为零；BTC 六项和为零，债务仍为 2 satoshi，不能以“零余额差异”声称零债务。反例：N 偷改为 2 会错误地产生 R=0、客户 BTC=100,000,000；缺一侧 fill、重复 repay、浮点 2.0 轮、False 冒充零未决、孤立 posting 或 K+1 接纳单均应 fail closed。纯参考器尚未实现/运行；手算 fixture 的 `execution_status=NOT_RUN`。

实际 909 的 N=5400、K=4357 对应公式可得到 R=2086、orders/fills17428、matches8714、account commands26142、risk decisions34856、ledger events21791，与首终态 prefix 观察相容；此代入不是执行新 forensic audit，不产生新水位或成功 receipt。

## 具体源码拆分与实施门槛

建议新增独立 `tools/audit_completed_prefix.py` 作为仅离线 CLI；新增 `tools/prefix_forensic_contract.py` 处理严格 JSON、身份、manifest、边界与 receipt；新增 `tools/prefix_forensic_reader.py` 作为 future 私有只读 clone 查询器；新增 `tools/prefix_forensic_reference.py` 以独立 integer/Fraction 重建完整核对；新增 `tests/test_prefix_forensic_contract.py` 与独立验证组的故障/差分用例。原 `managed_soak_observer.producer_audit`、`benchmarks.run_managed_soak.audit_job` 和旧 result schema 不改。

第一实现里程碑只实现不 import SQL/UTA 的纯 contract/reference 及上述手算例，固定 source commit 后申请明确 CPU/时限的一次纯验证；对 bool/float 别名、规范 birth、巨整数、缺/重复事件、同 PID 新 birth、未知动作和零/超前边界分别留首反例。下一里程碑由独立组评审 kernel 只读/数据库快照/资源方案，再申请一次新合成临时库 E2E 验证。最后才可提出对**明确已授权的原冻结数据副本**取证的具体 GO；三阶段均不能用已有权限默认越过下一阶段。

Schema 只说明输出形状，不自行证明 `K<N`、公式、scope 真实性或金融守恒；这些必须由将来的严格纯参考器与实际只读证据验证。当前没有任何新审计能力被装进运行服务或被标为验收通过。

## 部署、回滚与签字

当前只交付规则/schema/标准例，无运行迁移或服务部署。后续工具独立版本部署在只读调查环境，只有 private-output 写权限；无自动定时器、无自动 resume、无生产 API 路由。回滚移除新 CLI/引用，保留所有输入/输出 manifest、原失败与私有副本；不得删除证据、冲正账务或清空未知动作来促成通过。

独立取证方法审查、金融规则签字、最终执行批准均为 PENDING。首终态独立审查由另一工作组提交，不能代替本新模式的审查，也不能反过来升级旧六小时结果。
