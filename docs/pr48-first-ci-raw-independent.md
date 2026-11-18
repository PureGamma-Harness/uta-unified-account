# PR48 首次 CI：独立 RAW 审查

结论分开记录：**RAW_EVIDENCE_BINDING_PASS_WITH_EXPLICIT_LIMITATIONS**；
**原候选的 relation-only 公开导出门槛未闭合**；两轮整体 CI 仍失败，
生产状态为 **NO_GO**。没有把新六方法通过、本地 SQL 或固定成功样本升级为整轮通过。

审查对象是本地未发布候选 a1b9a90cf66b5b96685042f48f049b6d79be0fdc。
本审查提交直接基于公开源码 C6ba5ba2e9334f30be949f368d036c96fe9857c30，
不让原候选成为本提交的祖先；不复制候选中的具体身份序号。

## 原件绑定与整轮结果

私有60原件共2715344字节，全部与原 PRIVATE-SEAL 及候选公开 opaque inventory
逐字节长度/SHA匹配，文件0600、目录0700。读取使用 NOFOLLOW/NOATIME 并检查
常规文件、canonical path 和读取前后状态。seal 为12768字节，SHA-256
944b5c59d817b62199437940637ef5ff84b171ef2a51eda64b238d8ed868e9f5。
HTTP headers 和 signed references 仅计算字节摘要，没有解析或导出值。

四份原 ZIP、全部28成员 CRC、各成员副本长度/SHA及提供方 artifact ID/slot/run
对应；两份 decoded failed-job log 与已保存 connector 内容的 UTF-8 字节相同。
候选五项 SAFE 文件共48506字节，物理原文也与其固定 Git blob 相同。
本审查没有重新取 API、下载、轮询或重跑任何 job。

push44283600389 与 PR44283882268 原生 run_attempt1 均 completed/failure，
各只有 Python3.12 job 失败，另三个成功。三份实际 unit 为：

| 样本 | Artifact ID | Tests | F / E / skip | Worker exit |
| --- | ---: | ---: | --- | ---: |
| push3.12 失败 | 14418437395 | 2055 | 1 / 0 / 0 | 1 |
| PR3.12 失败 | 14418841221 | 2055 | 3 / 0 / 0 | 1 |
| 固定 PR3.13 成功 | 14418413338 | 2055 | 0 / 0 / 0 | 0 |

三份 baseline worker 均为精确七字段，与 summary 的原生类型和值完全相等。
各371项 source before/after 摘要相同，逐项对应 C 的 Git 字节。
push 的 code_commit 为 C；两份 PR unit 为
e211e4b3d2b7e91db54a45baaae2cfd73331f539。
已存 provider merge 的 parents 为 base9b61e5f 与 C，
tree6ead209181fded3d164aa70a57bd2c928f0c73f8 与 C 相同。
没有声称重新下载了其它成功 unit 或 checkout 原文。

失败样本实际 Python3.12.16、成功样本 Python3.13.18，SQLite 均3.46.1，
不借用本地独立 once 的运行时或数据库来补本次 CI。

## 四个失败 footer 的阶段不同

1. push expired-lease 测试在 tests/test_readiness_sampling.py:253，
   预期 inactive-lease 异常已捕获，随后观察调用次数为4、断言要求1。
   原件没有全部四次 diagnostics 的内容，不能推导重试原因或锁持有者。
2. PR clock-rollback 测试的实际栈为调用点130到 activate:75，
   清除 halt 的返回仍为 true，尚未进入 clock-rollback 主体。
3. PR bounded-eventual 测试在 readiness_sampling.py:358，
   有意 fence 争用释放后，同 SID1 重发仍 publishing=true，
   error=market_fanout_incomplete；尚未进入后续 SID2 场景。
4. PR 同名 expired-lease 测试在 :251 的期望异常匹配失败。
   原内层 diagnostics 显示 READY report PID 与当前 owner PID 不匹配，
   report 的 generation 落后于当前 owner，尚未到 :253 调用次数断言。
   该身份谓词与 helper:79 的源码相符；这里没有把静态对应冒充另捕获的 helper 栈帧。

原 footer header 行 SHA、选定 assertion 行 SHA、实际仓库栈帧及对应 Git 源码行
均重新核对。机器记录额外保存源码文件与行 SHA，不保存真实 PID、nonce、boot
或 generation/shard 数值。四项底层运行时原因均保持 **UNDETERMINED**，
不归并为旧 SH 捕获/五秒恢复故障，也不能证明资金费变更绝无时序影响。

## 新六方法及 package report

新增 FundingArithmeticTests 三方法与 FundingLocalSQLTests 三方法，在三份 unit
原文中各有唯一 ok 行；原行序号/摘要匹配，共6个唯一 ID、18次观察，
不是18个不同的方法。CI 临时数据库未在这些 bundle 中归档；
本地 SQL0e 不能替代本轮失败或临时库证据。

同一固定 PR3.13 slot 的 small report14418113095 为
PROVIDER_SMALL_REPORT_ONLY。19成员 CRC通过，7项报告 checks=true，
64项 runtime SHA匹配 C，6923项 required 路径集合精确等于 C，
含全部58个变更路径；报告 sdist6930成员、missing/mismatched均空。
installed report 的8项测试、8条 returncode0命令及原8条 ok 对应。

但 installed 模块清单只有25项，没有两个新增 funding 模块；
因此不能宣称已安装的 funding 操作功能通过验收。
没有下载大 wheel/sdist 容器、重新构建或安装，也没有独立验证这些 binary。
full qualification 与 installed-funding-operation qualification 均为 null。

## 公开导出的具体差异

候选的有限 credential/auth/private-key/signed-query/UUID/独立32hex检查为零，
没有发现实际 PID、nonce、boot 字符串或 signed reference 被公开复制。
这些模式检查**不能替代**本任务更严格的 relation-only 导出边界。

候选文档和 failure-phase-projection.worker_generation_relationships 实际保留了
具体 generation 整数与 shard。即使它们属于合成测试中的低整数 ordinal，
仍超出了“只公开 mismatch/先后关系”的要求，故原候选公开导出门槛未通过。
本审查只保留 PID相等性=false、report-generation落后=true 这样的布尔关系；
不再次复制那些序号，也不修改原候选或私有原件。

Root 已决定从公开 C 另建 SAFE-only 交付分支，以关系布尔和 redaction receipt
替换这些字段，且不让原候选成为公开祖先。该新导出仍需独立复核；
本记录不会提前为尚未审查的新分支签字。后续修订须保留 a1 原候选与私有首原件。

本次仅只读字节、严格 JSON、CRC、Git、源码文本和安全 literal 解析，
没有目标 import/compile/test、SQL、PID/proc、signal、网络/API/下载、
benchmark 或目标 child。没有读取其它 authority、DUE 分支或新 SQL。
新增报告可单独撤回，不改变金融源码、数据库、账户权威或原 CI 首次结果。
