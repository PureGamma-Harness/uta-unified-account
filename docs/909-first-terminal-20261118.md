# 909 六小时任务首次实际终态：NO_GO

冻结源 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0` 的原任务已于 `2026-11-18T00:53:08.132241315Z` 结束生产者控制流程，状态为 **paused**。原 active elapsed 为 **19,443.305304647s**，完成 **4,357 / 5,400** 轮；没有达到 21,600s 和完整轮数门槛。本次不续跑、不补时、不缩短新门槛，旧 887 首次 24h 失败保持原结论。

## 直接证据与结果边界

原 `control/collection-errors.jsonl` 只有一条资源事件：`observer_output_budget_exceeded`，测得输出 **2,157,259,397B**，超过原 **2,147,483,648B** 预算 **9,775,749B**，`RESOURCE_NO_GO_OFFICIAL_DRIVER_DRAIN`、`signal_sent=true`。测量范围是原 `control_and_observer_except_validated_private_clones`；事件明确 `financial_corruption_inferred=false`。记录没有显示金融腐败，资源失败不能证明资金丢失，也不能证明金融安全门槛已过。

| 原记录 | 实际结果 | 可验证范围 |
| --- | --- | --- |
| producer-result | exit 2，stdout_complete=true，paused | 19,443.305304647s；4,357 DONE；145 worker / 14 parent 故障；无未完成 step/fault；final_audit=null |
| final-before-cold | exit 0，stdout_complete=true，response 存在 | stable_boundary 4,357；原 observer prefix golden compared=true / passed=true；final_evidence_eligible=false |
| strict-producer-cold-result | exit 1，stdout_complete=true | ValueError；未发行 producer cold receipt；没有可用的成功冷审计证明 |
| final-after-cold | exit 0，stdout_complete=true，response 存在 | 仍为 4,357 prefix golden PASS；没有 final_reconciliation；final_evidence_eligible=false |
| final-summary | COLLECTION_FINISHED | financial_final_evidence_eligible=false；overall=false；official drain=true；fault schedule=false |
| live-coverage | NO_GO，321 samples | 16 次稳定 golden；305 次 inflight/unproven 未比较；多个原 block 缺 required golden；actual duration 不足 |

前后观察 JSON 各约 12.77MB，使用原 `final_once` 的 64MiB stdout 上限；实际两个回执均完整保留 response。早期“可能因默认 4MiB 截断”的猜测未被原记录支持，不能写成原因。原生产者 `logs_verified=true` 是其自身日志检查结果；本次前后观察没有独立终态 `final_reconciliation.logs` 或 cold reopen 证明，不能将两者合并为完整终态验收。

原监督器 `310035/birth8086947` 在首次封存时为 Z、PPID1、编码退出状态 0；原 driver/observer wrapper/CLI 身份均已消失。监督器 exit 0 表示完成收集，不覆盖 paused、冷审计失败或金融资格 false，也不意味着该 zombie 已被父进程 wait/reap。

## 已完成前缀的金融观察

前后原 observer 报告均为稳定轮边界：17,428 orders、17,428 fills、8,714 matches、4,357 次 partial cancellation、26,142 条 account commands、34,856 条 risk decisions、21,791 ledger events，与 4,357 轮的原合成公式一致。剩余已种本金为 **2,086 satoshi**；无活跃订单、仓位残余或 retry alerts；golden errors 为空。

这些是原观察者对**已完成轮次前缀**的核对报告。本封存仅哈希和解析已有 JSON，没有重新读取账本或独立重算任何资金。它们不证明完整 5,400 轮、物理重开、成功冷备份审计、完整风险引擎重执行或完整业务事件状态回放。原 progress 的 final_audit=null、两个观察的 final_reconciliation 缺失，以及 cold receipt 文件缺失必须继续保留为证据缺口。

## 冷审计错误的限定来源绑定

原 cold response 记录 `ValueError` 与 digest `4a5ed95de5ca7c7837583d12ce1ff661d7aa5b80428619cfa19821d19f1cf37b`。对固定源码的纯 AST/哈希检查确认：该 digest 与整个 observer 模块中唯一的消息 literal `producer_audit_requires_other_final_checks_passed` 对应，位于 `tools/managed_soak_observer.py:704`。原错误处理采用 `sha256(str(error).encode()).hexdigest()`。

因此可将该次冷尝试限定为“原 final-check 前置拒绝”的来源绑定证据；本次没有执行 audit 函数，没有重新生成 receipt，也没有通过 paused 状态猜测一个未验证异常。它不构成资金腐败或已完成冷审计的证据。

## 首次封存方法与原始材料

独立只读批次于 `2026-11-18T00:59:54.529572Z` 开始，CPU3，15s 进程上限，实际 **565,719,784ns** / exit 0。一次读取 16 个固定元数据路径，使用 O_NOFOLLOW/O_NOATIME，校验普通文件、64MiB 最大记录及读取前后 inode/size/mtime/ctime 一致；未打开 SQL、未启动 observer、未操作任何业务进程。每个原文件的 SHA、大小和稳定性记录在 [safe-first-observation.json](../evidence/909-first-terminal-20261118/safe-first-observation.json)。小原件至多 1MiB 的副本保存在外部 0700 私有目录，未发布；大型 JSON 只记录原始哈希，没有盲拷 2GiB timeline、私钥、nonce 或数据库。

原 collection-errors 414B / SHA `de22885b024158a602e6dafd2e44833573b79ce3bb5dfbaf42fc6a32533d4bcd`；原 final-summary 5,647B / SHA `7e8a571a9af3c774b969bc057442451d8d5aacda460c028a824864eea069f8d6`。公开文件仅包含合成指标、允许字段投影、哈希、封存脚本与实际执行记录，见 [manifest.json](../evidence/909-first-terminal-20261118/manifest.json)。

## 部署、恢复与回滚

本交付仅增加证据和文档，不修改运行源、服务、schema、风险参数、资源预算或已存在数据。保留整个原任务目录、私有克隆、日志、密钥与全部首次失败；不重新生成旧终态文件，不删除或压缩原始材料来改变预算结果。撤销本证据提交只移除新增公开报告，不能回退历史账务或将本次 paused 改为 completed。

资源输出量与稳定 golden 覆盖缺口由后续独立版本修复及验收，任何新任务都需要单独源、计划和原始结果，旧失败不折抵。当前本地低速合成测试不满足万笔容量、多节点 HA、完整产品或真实资金生产验收；本次总体仍为 **NO_GO**。
