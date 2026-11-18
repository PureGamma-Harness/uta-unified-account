# Native controller 与 guards6 公开候选

状态：**LOCAL_CANDIDATE / NOT_PUSHED / NO_NEW_RUN / NOT_PRODUCTION / NOT_10K**。本候选从已公开 PR49 `c3e937a967711cd5cae7293ac3bf63c8260d8528` 建立，只按有限白名单复制 Git blob 字节。没有 merge/cherry-pick 私有 CODE/RAW 分支历史，没有执行目标 import、编译、测试、SQL、proc/PID检查、worker、native 或网络。当前等待另一组 CODE/privacy 审查，本提交不启动任何运行。

## 交付内容与源码闭合

[export-manifest.json](../evidence/candidates/native-public-safe/export-manifest.json) 列出44个精确导出文件、来源commit/blob/mode、大小、SHA-256和用途，共296169 bytes；本页及3个新候选JSON另行生成。6个 native benchmark 源来自固定 be373 CODE；另外5个 guards6源码/合成fixture来自固定 guards6 CODE。所有61个UTA运行时文件保持公开PR49原样。

唯一当前70项源码依据是 controller-001-003/source-manifest.json，SHA-256 `e3c62d9ee7f2aac50eb1335835c60d45ca5fdd5eef71fb0d5a62150f10559c4e`，对应历史plan `a844eb613147ac52a65cc648f59c9cc408b8507e6459ad5d485695f5b2e41dbf`。64项与公开base相同，其余6项从指定CODE原字节导出，70/70逐项核同。guards6 binding为 `c38550ace6e248c6229698a2fb16cf611fddfe19864ea30e58486015c7463beb`，其15项源码/数据同样逐项核同。详见 [source-closure.json](../evidence/candidates/native-public-safe/source-closure.json)。这些是字节与静态依赖核对，不是本次功能执行结果。

旧 source-manifest-native-host.json、旧native plan/manual/unit/static/exact文件保持原字节，明确为 **HISTORICAL_NOT_CURRENT_70 / DATA_ONLY_FIXTURE_REFERENCE**：旧70 manifest只有67项匹配当前候选，pilot/native-host/owned-workers三项仍指向更早字节，旧unit fixture也指向更早的host/test版本。不得用旧manifest或旧entry启动当前native或声称当前70闭合。最初一次行政校验误用了旧manifest，因此断言拒绝；随后识别并使用正确controller manifest，没有修改旧资料、目标运行或重试。

## 历史意图与真实结果分开保留

所有旧CODE计划、exact argv、通用源码/capture绝对路径都是 **HISTORICAL_CODE_INTENT_NOT_CURRENT_AUTHORIZATION**。原文 execution_authorized=false、actual_attempts=0等字段记录当时CODE阶段，不能抹去后来保留的首次native失败或guards6首次fake测试。旧roots已使用、封存，**DO_NOT_EXECUTE / DO_NOT_REUSE**；计划里的路径和argv不是可直接执行的部署命令。

原 [native首次失败](cross-native-first-fail-c29da80.md) 与 [独立RAW结论](native-first-c29da80-independent-raw.md) 原样保留。外部见证host exit=1；34个实际offered中观察到25个持久接纳回执、8个业务拒绝和1个控制行情拒绝，首次fault为router_halted。**未完成重开逐笔对账、未通过功能/容量门槛、没有重试。** 不能把25条回执称为25条已独立对账成交或容量成绩。

另保留guards6的5份既有SAFE文件和 [两份独立复核](native-guards6-first-independent-raw.md)：它只证明原有限6个合成mock方法的保留结果与退出见证，不证明native80、新源码运行、任意C扩展沙箱或生产可用。原作者报告的pending-independent字段也不重写，独立结论通过追加的独立记录表达。

[privacy-review.json](../evidence/candidates/native-public-safe/privacy-review.json) 是作者白名单自审，另组审查仍待完成。没有原始DB/WAL/SHM/ZIP、实际session/nonce/PID/boot、私钥/capsule/TLS、实际生成绑定、原始control副本或私有运行位置。源码的固定禁止PID集合和显式synthetic fake身份是测试规则，不是实际进程身份。既有SAFE中的匿名摘要、计数、源码hash和公开见证元数据仅为证据来源。

## 部署与复现前置

本候选当前只支持审查和静态字节复核。可以检查Git父提交、export manifest中44个blob与当前文件SHA、controller70与guards15逐项值，并对Python源码做AST解析；禁止将这些行政检查描述为目标单测通过。历史 resource-import-map 中13个固定CPython标准库源记录及解释器路径是环境依赖，不是已复制的二进制或当前runtime证明，不能据此声称可在任意机器原命令复跑。

另组CODE/privacy通过后，若要试跑，必须另立**新独立namespace、新runtime/source inventory、新不可变plan/exact argv及预算、首次失败终止/封存/外部exit见证与清理边界**，再审查并取得对应运行授权。原plan、原roots、旧root授权和旧源码scope均拒绝复用。首次FAIL原因及任何修复需独立代码审查，新运行保留自己的首次样本，不能替换原失败。该流程未在本提交执行，也没有提供暗中可执行的新plan。

真实功能验收还需完整接纳/预占、真实撮合、仓位和资金账提交、重开逐笔对账、结果未知恢复及故障证据；万笔容量另需独立开放环、至少30分钟与长稳、混合负载和用户全部门槛。此候选无HA、RPO/RTO或生产资金批准。

## 回滚

本次只增加benchmark/fixture与证据文档，未改UTA运行时或任何持久authority。回滚候选commit即可移除新增文件；不改写原CODE/SAFE/RAW提交或封存原件。以后若经独立计划运行，应保留已确认经济事件和原始失败记录，先停新增风险并查询原命令结果，再按该新计划的恢复/迁移手册处理；不得删除历史cut/账本或借旧计划恢复写入。
