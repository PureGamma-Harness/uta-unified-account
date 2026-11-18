# PR48 relation-only 导出：独立有限差异复核

结论：**RELATION_ONLY_SAFE_EXPORT_DELTA_CLOSED_FOR_PUBLIC_DELIVERY**，
只适用于 e197b89e9d0f88108e93e2d816f311bbfa398603 的限定公开导出。
历史候选 a1 的 export NOT_CLOSED 不回写；本次新交付的导出边界已闭合。
两轮 CI 仍失败，生产仍为 **NO_GO**。

该交付 parent 是独立 RAW 记录 d5ccc4cb12e03a0989775e93736ab0303d896632，
其 parent 是公开 C6ba5ba2e9334f30be949f368d036c96fe9857c30。
a1 不是交付或本审查的祖先。C 到 e197 只有9项 docs/evidence 新增；
financial runtime、tests、tools、CI、config 与 build 配置差异为零。
没有把包含具体身份序号的本地候选合并或 cherry-pick 到公开祖先链。

五个候选 payload 的旧长度/SHA、五个交付 payload 的新长度/SHA，
以及 d5 原三项 SAFE 的长度/SHA 均与6842字节 redaction receipt 精确对应；
receipt SHA-256 为
ccd2d519bdf8a21230c44e9be40ba35a6a74404e5f419bebb979383c280cc0d9。
五项合计48506变为48547字节，其中三个文件逐字节不变。

两个改动文件的复核如下：

- JSON 只改 /failures/3/worker_generation_relationships/0：
  删除三个数值 binding 字段，添加 mismatch 与 precedes 两个严格布尔。
  两个布尔直接以原候选数值的不等/小于关系复算为 true；
  本报告不复制原数值。深拷贝原 JSON 做这唯一变换后，
  精确重建新 JSON 的语义和最终序列化字节。
- 文档只替换一个连续片段，删除具体身份序号，改述 report-generation
  早于当前 owner 的关系。匹配片段与同一原 JSON 关系对应，
  替换前后其余文档字节完全相同。

所有其它 JSON 字段、数组长度、失败阶段、原行/源码 SHA 和调用计数均保留。
receipt 只有路径、摘要、变换说明及有限事实，没有旧字段值。
九个交付 payload 的 Git/物理常规文件字节一致；
有限七类模式检查均零，递归检查未发现数值 generation/shard 身份字段。
这只是限定输出检查，不是全仓库安全审计。

原60私有文件仅额外做长度/SHA/模式的摘要复核，总2715344字节未变；
PRIVATE-SEAL12768字节的原 SHA 仍为
944b5c59d817b62199437940637ef5ff84b171ef2a51eda64b238d8ed868e9f5。
没有重审原始财务/运行时语义，也没有解析 headers、signed references 或输出身份值。
导出方 receipt 关于不读取私有原件的字段描述其自身动作；
本次独立复核的额外 digest-only 读取在机器记录中单独说明。

完整 RAW 结论依旧引用 d5，不重新运行测试：
push 的1F与 PR 的3F及其不同前置阶段、全部原因 UNDETERMINED、
6个唯一新增 funding 方法的18次成功观察都未改变。
安装模块清单没有两个新增 funding 模块，installed-funding-operation
qualification 和 full qualification 均为 null。固定成功样本或本地 SQL
不能覆盖两轮整体失败，公开此证据也不构成上线授权。

本次没有 API/网络、目标 import/compile/test、SQL、PID/proc、signal、
native、benchmark、CI rerun 或目标 child。旧候选、首原件和 d5 内容未改。
本审查仅新增这份说明与有限 JSON；撤回它们不改变任何金融或数据库状态。
