# 前缀因果修复：独立 CODE 与首证据绑定审查

固定修复 `0c04590c8e8bcf75c7fb7e5b69b430031a24160e`，首证据 tip `b363a8ac84870c8c73ea5de4e27a2993217cc0a9`。**17e 独立首批的四个已知 finding 按 CODE 关闭。** 原25 PASS、独立4 PASS/4 FAIL均不改；本审查不执行任何测试或实际取证。

## 修复范围与因果规则

逐完整 journal event 累积 gross 分量后，修复核本金债务/应收都非负且等额，customer USD/BTC 与 pool BTC 非负。custody/capital contra 仍可为负。这正确限制了本 profile 的零 genesis，不把已有期初债务账户合法先还旧债错误归为非法。

另设 bootstrap/round 拓扑：全部六项 genesis 义务完成后才能出现 round effects；同轮 open 两侧完整后才进入 close，两侧 close 完整后才偿还该轮本金；该轮偿还之后才推进下一轮。逐业务 ID 归属与原 round/phase 关联，不依赖单纯最终 totals。

独立 genesis deposits 不强制唯一排列；同一 open/close pair 的两个 fill side 也不强制任意先后。因此修复没有把已证明合法的交换操作错误拒绝。未知 opening-state 仍不能通过这个固定 zero-genesis profile；需要明确的新版本及被验证的期初状态。

自称 `uta.completed_prefix_forensic_receipt.v1` 的输入 limitations 被限制到19f完整枚举，原未知标签反例关闭；这没有把旧 receipt schema 套到独立 synthetic result/error envelope。输出依然是 contract-consistent 的合成声明核对，真实 quiescence、认证、日志链、SQL和 forensic audit 全部 false，不产生实际 PREFIX_VERIFIED。

上述 CODE 结论关闭已知四例，不声称完成所有状态空间或完整业务重执行。真实 writer 闭包、kernel 只读输入和一致 WAL/快照方案仍待证明。

## 原件绑定

首执行记录的4项 Git blob 输入逐一对应固定修复 commit。核心模块、新focused测试和独立literal/oracle定义在首证据 tip 与修复 commit 逐字节相同；设计文档在首结果后增加结果说明，与原 source blob 区分记录，不能把更新后的文档当成原运行输入。

已有首 stderr 明确10项 `ok`，10 tests / 0.011s / OK；execution 的 exit 0、外层114,441,964ns对应。这是作者新focused首结果的只读核对，独立审查者没有重跑新10、原25或独立8。新测试仅提取已审独立文件的常量和fixture/oracle函数AST，没有调用其原8个test methods。

旧作者首证据4文件与3b0a9ab逐字节相同；独立首FAIL证据7文件与17e4542逐字节相同。原 producer/strict audit源码、UTA runtime tree及19f receipt schema均未改变。完整绑定与SHA见 [独立记录](../evidence/reviews/prefix-causality-code/code-and-raw-bindings.json)。

## 部署与回滚

本 OWN 只增加独立文档与绑定记录，无schema、参数、服务、账户或原数据变更。回滚只移除本 OWN 新文件；原25、新10、独立4 FAIL和原六小时NO_GO全部保留。未执行SQL、observer、clone、实际audit、原数据、crypto、网络或业务进程；生产和真实资金批准仍为false。
