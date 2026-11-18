# 前缀纯契约独立验证：四项反例

固定 candidate core `9f74dce34fd856fc2bc6e04b6c310a30e93ec10a`、首证据 tip `3b0a9ab0d9b8ed9719dad0328076aa5b17a1bdc0`。独立新批次 **8 项：4 PASS / 4 FAIL / 0 ERROR，exit 1**。作者原 25 PASS 和本批首 FAIL 均保留；本次不修改作者文件，也没有重跑任一批次。

## CODE 审查结论

688 规格审查所要求的权限分离已落实：结果为独立 synthetic schema，真实 quiescence、原 manifest 认证、加密日志链、实际 SQL/forensic 审计均永远 false；输入自报 checks/manifest 不会生成实际 PREFIX_VERIFIED。原 strict producer audit、原终态 gate、原19f schema保持原样。逐命令/控制 origin、双边 fill/match、逐事件 posting、最终 gross owner/asset 与余债的校验有实际覆盖。

但 `_journal` 只核全体业务集合、每事件 posting 形状、连续 ledger sequence 和最终余额，没有核固定 profile 的逐事件可达状态。把事件移动并重新编号后，最终所有 gross 分量与业务 ID 仍相同，但在起始为零的封闭合成账本中会出现尚未资金化的客户现金、pool 现金或负本金债务。该缺口不能通过期末守恒发现。

## 独立参考域与四个反例

参考采用全新 N=3/K=2 literal fixture，不调用作者 fixture、expected_budget、UTA/生产金融函数。原始域明确为：六个 genesis 事件之前全 owner/asset 余额为零、没有预存债务或 pool 资金；唯一 6 satoshi BORROWED 是 bootstrap，之后每轮偿还2。该规则**不能泛化为任意已有债务账户的还款必须排在某笔新借款后**。

独立整数参考按 journal sequence 在每个完整事件后累计所有 posting，要求客户/pool 现金及本金应收不为负，本金负债分量不为正，最终完整 owner/asset map 和余债2与手算相同。custody/capital contra 分量不套现金非负限制。

| 合成修改 | 独立参考原因 | 候选结果 |
| --- | --- | --- |
| 第一轮 REPAID 移到唯一 genesis BORROWED 前 | 负本金债务、应收为负 | contract_consistent=true，FAIL |
| 唯一 BORROWED 移到 POOL_FUNDED 前 | pool 现金为负 | contract_consistent=true，FAIL |
| 第一笔 Alice fee 移到其 genesis USD deposit 前 | 客户现金为负 | contract_consistent=true，FAIL |
| 输入自称19f forensic v1 receipt，添加未注册 limitation | 与该 v1 receipt 的枚举域不符 | contract_consistent=true，FAIL |

第四项只针对输入内明确声明的 `uta.completed_prefix_forensic_receipt.v1`。不把旧 receipt schema 套在新 synthetic result/error envelope 上：后者用于忠实表达 REFUSED/K0/failed 等状态，仍须独立保留。本项没有要求原19f schema在本轮被修改。

正控允许 Alice/Bob 相互独立的 genesis deposits 交换顺序，不把全部事件强制为一条唯一排列。其余通过项为完整 N3/K2 全部实权 false、gross 余额的浮点别名拒绝、未知 control origin 拒绝。四个反例不证明完整事件重执行，也不意味着原真实运行存在这些坏事件。

## 首次执行证据

独立预执行提交 `12f6ff9b75725c1837714d48f33d06dcff15dfe7`，脚本 SHA `becbe5517b4cc87fcb62f55c94846e36379df44980f7cc583d47926c7fa89c88`；candidate SHA `13269c504e67d2667b3a225377b54bc60d82a19f5ba4d8117e4bd7593a41272c`。CPU1、10s 上限，实际外层 **109,582,576ns**、unittest **0.011s**。stdout 为空，完整 stderr 4,504B / SHA `58ef3476a16557cff9108e4dd63c16c286fa039c5dfe359208e406a762ad8162`，见 [首原件](../evidence/reviews/prefix-pure-independent/first.stderr.txt)。

执行仅为新合成内存数据、独立整数参考和候选纯验证函数；未执行 SQL、实际取证/审计、observer、原数据读取、crypto、网络或业务进程。新参考保留输出 false 权限，未生成新实际 forensic receipt。真实 writer 闭包、只读 WAL/一致物理输入及完整日志验证仍未证明。

## 修复、部署与回滚

最小修复应按本固定 bootstrap/profile 明确 genesis 与 round effects 的因果边界，核每事件后的 gross 资金与本金状态，保留合法独立 genesis 顺序，并将自称 v1 receipt 的 limitations 约束到其已声明枚举。新源码须经新的具体小批次及独立审查；不得覆盖本首 FAIL 或把最终余额正确当作完整因果证明。

本 OWN 仅新增独立脚本、计划、首次输出和审查，无运行部署、schema/风险参数或数据迁移。回滚移除本 OWN 新文件，保留作者25首结果、本批8首结果、旧strict gate及原六小时 NO_GO。当前纯候选与实际平台都未因本交付获得生产或真实资金批准。
