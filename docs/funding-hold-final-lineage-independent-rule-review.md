# Final funding lineage：独立有限规则审查

固定公共规则 `69a3e32e9d267295f223671e62f17b2f9e71eb70`，parent86b3。
结论：**SPEC_POLICY_CLOSED_FOR_D1_SUPPLIED_DATA_ONLY / NOT_RUN**。
这项本系统前向澄清可作为新版本参考/模型的受审输入；不关闭原 612 的
RV2-B1 CODE，不构成实际状态转换、差分或 D2/生产批准。

两项规则工件物理/Git bytes、SHA 一致，差异仅新增47行文档和21行JSON。
本轮仅读取这些公共规则、2bb/8008/061 的既有定义与固定来源。
没有修改、导入、字节编译、调用或生成目标/参考/测试，没有 SQL、读钟、
proc/PID、actor、网络或 CI。机器记录见
[review-69a3e32e.json](../evidence/reviews/funding-hold-final-lineage-independent/review-69a3e32e.json)。

## 规则自洽

直接 registered→final 没有前置 U，exposure_ref/cap_ref 必须均为 null，
final_ref 必需。经 U→final 则要求最终两项 refs 与 immutable 历史 U 的完整
ContentRef 逐字段相同，final_ref 另必需；适用于 payable、receivable 和 zero。
缺失、partial、changed、foreign 或无 U 却带 lineage 均显式拒绝。结合先前
same-duty/rule-scope 类型检查、history/revision 与 complete expected-stage CAS，
这是确定的提供数据一致性规则，不依赖“填上看起来相同的 hash”猜测来源。

当前061的 nullable-or-ContentRef 字段形状能表示两种合法路径，无需改 DTO
字段。新增的是明确语义约束，不能据此说该要求早已被061编码，也不能在
bridge 中把旧 null 负例自动修成保留 refs 的正例。旧612强制 null 的事实
及原e6/061/612历史必须保持；新作者从这项公开规则另交不可变源与输入。

引用保留与金额计量是不同字段。聚合只读取 active.kind/amount，历史 U 不贡献，
因此给定 U600→P246 的 P=246/U=0/H=246；转 N246 为 N=246/H=0；zero 为
P/U/N/H=0。三者仍保留 E/C 引用用于与历史比对。这些是手工规则推导，
不是已执行的参考结果。N 不抵 H、原 cap 上限、final immutable、history
长度和 scope 规则都不改变；引用也不产生第二次会计负债或支付权限。

“prove lineage”只可解释为对**当前提供历史**的内部一致性，不代表内容真实性、
cut 来源、审批、批准政策、持久唯一或真正历史完整。文档同时明确这些 D2
义务；不能从匹配两个任意给定 ContentRef 推导外部真实性或原子提交。

## 新 CODE 的必要验收

新版本须定义 direct→P/N/zero 无 lineage 的正例；U→P/N/zero 保留完全匹配
E/C 的正例；以及丢一项/丢两项、改变 E 或 C、foreign duty/scope、没有 U 却
附 refs、不可变历史被替换的负例。stage 输出全部字段必须比较，不能只看
P/U/N/H 相同。原 complete expected Stage/revision、cap breach 和 final
immutability 负例继续保留；新规则不为其开例外。

这些门槛均 NOT_RUN。尤其原612及其 generator 尚未修复/合格，未来新代码、
bridge、有限执行 caller/source pins/资源与第一次 RAW 必须另审。本规则审查
没有执行 GO、decoder equivalence、真实 ACK/outbox、全入口 fence、APPLIED、
整期原子性、恢复、容量、真实资金或生产签字；D2无条件 BLOCKED。

本交付仅新增两份 SAFE 审查资料，不改69/2bb/061/e6/612、runtime 或任何
历史结果。回滚仅 revert 审查；规则本身若回滚，也必须保留所有旧源码及
已确认经济记录，不得倒改一次成功/失败原件。

行政事件单列：创建 review worktree 后，一次仅针对上述两个固定规则文件的
`git restore` 错在作者 workdir 发出；随后已在正确 review workdir 物化。
事后只读核作者 HEAD69/clean、两文件 byte SHA 与固定 Git 相同。没有观察
事前 mtime，不能声称 inode/时间元数据未变，也不把它写成“从未对作者目录
发出写命令”。未触参考/runtime/数据/计划或任何目标执行。
