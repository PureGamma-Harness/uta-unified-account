# Compact-v2 独立审查：四项类型别名反例

审查固定 component code `e497e22f4f7f48f5c0c2abd53fa8e9a9bd0893c4` 及作者首证据 tip `00989ce23bd0db5d03485626ea6fa9693fc4e508`。本 OWN 不修改候选代码或作者首批证据。**本轮结论为 NO_GO：独立首批 8 项中 4 PASS、4 FAIL、0 ERROR。**

## 已复现的完整性缺口

`restore` 以 Python 字典相等性比较不可变 publication 与传入 compact。Python 中 `1 == True == 1.0`，而这三者是不同的 JSON 数据。下列四个小合成修改均被独立 canonical JSON oracle 拒绝，但候选 `restore` 接受，违背“可见字段变化必须拒绝”的契约：

| 修改字段 | 原值 | 修改后 | 独立 oracle | 候选 restore |
| --- | --- | --- | --- | --- |
| summary.commands.control_commands | `1` | `true` | 拒绝 | 接受，FAIL |
| report_version | `2` | `2.0` | 拒绝 | 接受，FAIL |
| synthetic | `true` | `1` | 拒绝 | 接受，FAIL |
| summary.commands.total | `3` | `3.0` | 拒绝 | 接受，FAIL |

本反例涉及报告传输完整性，不能据此推断原运行资金损失或已获金融权限。修复须使用保留 JSON 类型差别的比较，并在新源码上独立验收；原首次 FAIL 不得替换为重跑结果。

## 独立参考与实际结果

参考展开器仅按文档协议独立实现 canonical JSON、带 domain 的 CAS hash、节点读取、in-order 展开、节点计数和完整报告指纹验证，不调用候选 `_decode`、`_array`、`restore` 或其 hash/canonical 辅助函数。候选仅用于生成合成封包与接受/拒绝的差分侧。手工输入共 3 条命令：2 条账户命令、1 条控制命令，各 1 条 SUCCEEDED、QUARANTINED、PENDING；额外原始字段也必须完整还原。

另外四项通过：独立完整展开和手算计数；缺节点/坏 hash 均拒绝；新增 item 大小限制前确已完整调用 consumer；参考 parser 拒绝 duplicate keys、NaN 和 Infinity。参考域为有限、普通 JSON 对象，不声称任意深度输入、非 JSON Python 对象或通用 hostile parser 的完整行为。

预执行源码冻结提交为 `cca8cf094ff7be73da3296d05d6d9e652fbd62d6`，独立脚本 SHA `a57539141d67d41494a5b91c8a69364327a0185a71c162951eb6a1a8a8456cda`。唯一新批次 CPU1、10s 上限、最多 3 条合成命令、参考最多 200 次节点访问，实际外层 **92,998,920ns**、unittest **0.006s**、exit 1。stdout 为空，stderr 4,749B / SHA `2e779c7f40748852babc9019c56a4d063966f576b2b2ba553d6a1fbf6045dfdf`，完整保留在 [首次 stderr](../evidence/reviews/observer-compact-independent/first.stderr.txt)。没有重跑作者 8 方法或本批次。

## 稳定树与边界的 CODE 结论

稳定 anchor 的 Cartesian 树以输入顺序作 in-order，优先级不依赖记录 offset。对唯一、稳定 anchor 和受 64 层限制的树，插入或改变单条记录仅改变相关 fringe/祖先，未变子树的 canonical bytes 和 CAS identity 可复用。这为**记录节点**的条件性 `O(N+(I+U)*H)` 存储量提供依据；重复 anchor 的 occurrence 重排、批量历史修改、非稳定标识、广泛字典变化不在低放大承诺内。

编码每次仍完整扫描全部历史，并递归访问全部记录节点；DirectoryStore.put 还会查询已有节点。这没有证明 CPU、读取 I/O 或单次延迟为增量。小 N 的作者测量也不能替代完整规模的 CAS bytes、文件数量、写放大、恢复与故障测试。

新 v2 有原 legacy 不具备的导出域限制：单 array item 2KiB、树深度 64、array node 4KiB、full-reference node 64KiB、compact 16KiB。它们不是删除字段或缩短原 consumer 的许可。首负控确认一个原报告可以先被完整 consumer 消费，然后因 item 大小拒绝导出。集成必须分别持久保存已获得的金融分类/已知告警和后续 export UNKNOWN；格式失败不能吞掉已知 fatal、改变 classify_safely 的回滚语义、跳过 financial drain，或重跑同一个已消费 attempt。此 CODE/PURE 层尚未实现该运行时集成。

DirectoryStore 的依赖目录位于 `observer/report-v2-nodes`，自身 256MiB 逻辑载荷预算属于附加约束；不能从原 control+observer 的 2GiB 聚合预算中排除。实际 FS adapter 未执行，包含目录、pending、物理存储开销和失败残留的容量行为仍需独立验证。CAS 还原的是完整旧 report，不能从 hash 还原缺失的 SQL 行或历史事件。

## 上线、部署与回滚

组件仍是 API-only，legacy 为默认，原 observer/watch writer 尚未集成，因此不能宣称修复实际 2GiB 输出膨胀。已有 coverage 的两处显式 v2 拒绝仅避免把 display envelope 当完整 proof；外部 reader 必须先验证和还原全部依赖，再运行原完整 consumer。callback 的完整消费与安全动作目前是调用契约，不能由 callback 返回一个结果推断其真正完成所有安全动作。

本 OWN 仅增加审查脚本、计划、原始输出、结果和文档，无 schema/风险参数/服务变更。撤销本 OWN 只移除新增材料；保留 e497 作者首批 8 PASS、本批 4 FAIL 和旧六小时暂停结果。未运行 FS adapter、SQL、observer、watch、原数据、网络、crypto、CI 或新长测；生产与金融批准始终为 false。
