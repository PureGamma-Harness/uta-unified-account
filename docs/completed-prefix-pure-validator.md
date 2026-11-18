# 前缀纯契约验证器：合成 JSON 阶段

本版在原规格 `19f4b5d3981688898bd221a9af128c9cf768eab6` 之外新增独立 `tools/prefix_contract.py`，原规格、schema、首终态 d243 和 strict cold gate 均保持原样。独立 SPEC 审查 `688af1bc67adc4c32f816bfd9636d75fec3f2249` 确认 N3/K2 手算与前缀边界相容，允许纯契约实现；真实 writer 闭包、WAL 与数据输入前提仍未证明，不能开展真实审计。

验证器只接受 `uta.synthetic_prefix_contract_input.v1` 的完整合成投影。它只用 Python 的 JSON、正则及整数容器计算，不导入 UTA、生产金融核心、SQLite 或现有 golden 函数；不读取数据文件、调用子进程、联网、计算加密摘要或使用真实密钥。N、K、轮次、最小单位、计数全部精确 int，排除 bool/float，输入数字限 signed 64-bit、深度 32、节点一百万，原始 JSON 字节上限 32MiB。超限或畸形返回结构化错误，不包含原始错误文本或任意输入字段。

## 输出资格与拒绝记录

独立审查要求不能把自报全 true checks 或自算 manifest SHA 当作真正 quiescence/金融证明。本工具输出独立的 `uta.synthetic_prefix_contract_result.v1`，仅报告 `contract_consistent`、固定错误代码与全部 false qualification；`forensic_audit_performed`、`real_quiescence_verified`、`cryptographic_log_chain_verified`、`raw_source_or_manifest_authenticated`、`sql_or_original_data_read` 永远 false。它不会生成或修改实际 `PREFIX_VERIFIED` forensic receipt。

输入中的 receipt、writer 停止信息与 manifest-verified 字段全部是**合成声明**。验证器检查其形状、前缀范围、类型及相互一致性，不能认证声明真伪。合成输入 receipt 声称 PREFIX_VERIFIED 并不意味着本工具进行过该审计，输出继续明确 NOT PERFORMED。真实执行、数据库快照、原日志加密哈希链、风险重执行和上线审批仍需后续独立实现与验收。

另一独立审查还指出：原草案 receipt schema 对 REFUSED 状态也强制 paused/K>=1，无法忠实表达 running/failed/unknown/K0 的拒绝。原 schema 暂不修改；本版所有拒绝采用上述**独立 result/error envelope**，不伪造一个 paused 的 forensic receipt。未来真实工具必须版本化地解决通用拒绝回执格式，不能放宽 PREFIX_VERIFIED 所需条件。

## 纯验证内容

- N 保留原计划，严格 `1<=K<N`，固定 source/version/profile、USD/BTC 各 8 位，原状态 paused。完整 schema 缺/多字段、重复 JSON key、浮点或布尔计数都拒绝。
- 原控制器单 session、无 active round/未完成 step/fault、无 unknown action；writer token 为规范正 ASCII decimal，按 PID/birth 去重，同 PID 真新 birth 允许。这里仍是合成声明检查，不是 `/proc` 或租约验证。
- 每轮六个独特 account command ID 与四个订单、四 fill、两双边 match、八 decision 逐个关联，核对方向、部分成交后的撤余量、reduce-only、价格、费用及零 PnL。未知或 K+1 的动作、重复 ID、缺口、不完整回执拒绝。
- control lane 每轮两个合成投影记录，要求明确 origin、SUCCEEDED、result-known、无资金影响；market/activation 的 milestone log 逐条关联 control ID。不能因无 account_id 忽略控制义务。这里的两条 control 投影是独立合成 profile，真实 909 的 control payload/授权和完整事件归属适配器尚未实现。
- 独立整数预算计算 gross owner/asset 与剩余本金 `2(N-K)`；保留负债与应收，拒绝净额隐藏。每个 ledger event 序号、ID、业务归属、posting ordinal、每币守恒、每 fill 费用及每次借/还本金分录均核对，再完整重建 owner/asset 投影。跨轮补偿费用即使总余额相同仍拒绝。
- 日志仅是**新合成 milestone 投影**的连续序号与前驱序号、每轮开始/控制终态/DONE/paused end 检查，不是对原 gzip 日志或原 SHA 链的重放。独立 receipt 的完整字段、前缀数值、scope、全部 false qualification 和 required limitations 均校验。

手算 fixture 由独立 literal 金额与业务动作构造，不调用 reference budget。参考器用整数公式独立推导 N3/K2 的 11 项 gross balances、8 orders/8 fills/4 matches/16 ledger events/余本金 2 satoshi；25 个 unit methods 将合法例、类型/边界、重复缺口、未知 control、双边 fill、逐笔分录、补偿错误、receipt 与大整数等负控分开覆盖。代码先固定为 `9f74dce34fd856fc2bc6e04b6c310a30e93ec10a`，向 root 报告 provenance 后，按唯一 CPU1/10s 预算执行首批：**25/25 PASS**，unittest 0.076s、完整外层耗时 214,356,773ns，exit 0。原 stdout/stderr、Git blob 输入及执行记录保存在 `evidence/completed-prefix-pure-validation`。旧 12/18/14 批次没有重跑；没有 SQL、实际数据、observer、备份、克隆、审计、网络、加密调用或业务进程动作。独立代码/差分审查仍待完成，不能把作者 unit PASS 当成金融签字。

## 部署、回滚与后续门槛

本版没有 CLI 文件读取路径，没有服务、schema 迁移或金融权限变化；作为离线纯函数候选保存，不进入生产路由或原调查程序。回滚移除新增模块/测试/引用并保留本批源与证据，原 19f/d243/strict gate 不变。

下一阶段先独立差分审查纯 reference 与错误 envelope，再单独评审真实只读输入适配器、所有 writer 的静止证明、WAL/备份与资源计划。任何真实 SQL、备份、克隆、observer、旧数据读取或审计都没有由本次纯授权放行。
