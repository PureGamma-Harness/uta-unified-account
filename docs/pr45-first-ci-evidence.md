# PR45 首轮 CI：push SUCCESS，PR 因一个普通发布锁 ERROR 而 FAIL

精确 head 为 `e8c466a410e659b7b0de965bc052e34107b67d8d`，base 为 PR35 的
`9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`；PR45 保持 Draft。实际 PR merge
`d6866465f76647df4381342a05d99d92505407ac` 的 parents 精确为 base/head，
tree `7590c3dd052054451b09bfca5a6af0ead94cd551` 与 head 相同。两轮均 attempt1。

| 事件 / run | Python | job | whole结论 | unit 原件采样 |
| --- | --- | --- | --- | --- |
| push44271111043 | 3.10 | 134687656311 | success | 未取成功 unit |
| push44271111043 | 3.11 | 134687656819 | success | 未取成功 unit |
| push44271111043 | 3.12 | 134687656770 | success | 未取成功 unit |
| push44271111043 | 3.13 | 134687656864 | success | 唯一成功样本：2057 /0FAIL/0ERROR/0skip |
| PR44271166000 | 3.10 | 134687835587 | failure | 唯一失败样本：2057 /0FAIL/1ERROR/0skip |
| PR44271166000 | 3.11 | 134687835422 | success | 未取成功 unit |
| PR44271166000 | 3.12 | 134687835432 | success | 未取成功 unit |
| PR44271166000 | 3.13 | 134687835208 | success | 未取成功 unit |

push 整轮 completed/success，PR 整轮 completed/failure；collector 不把其它
job 成功或既有 local/native/pure PASS 用来覆盖 PR whole failure。其它六份
成功 unit 未下载，不额外声称其逐条执行计数。终态后不再 polling 或请求。

唯一实际 ERROR ID 是
`test_durable_faults.ManagedProcessFaultTests.test_partial_publication_stays_halted_until_exact_publication_replay_completes`。
原 `tests/test_durable_faults.py:1627` 调用
`partial = self.router.publish_market(snapshot, timeout=.15)`，随后进入
`uta/durable_process.py:1532` 的 `_control._lock(exclusive=True, timeout=timeout)`。
异常链含 `BlockingIOError`，最终为 `uta.service.ServiceError`，到达
`uta/sharding.py:267` 原 raise 分支；其源码 literal 是 `router_busy`、503 和
`router control gate did not become available before timeout`。这是源码
literal，collector 没有从异常对象读取 runtime code 字段。

失败发生在普通部分行情发布的控制锁准入，属于另一个测试方法；不是新 SH
捕获目标失败，也不是该目标的五秒恢复断言。该失败方法的 AST 与 PR35 base
相同，生产 UTA、tools、config、build 和 workflow 对 base 均零差异。
具体持锁原因未由原 traceback 证明，记为 UNDETERMINED；未复现、探测 PID
或给旧 CI35/41、c98、8112 范围回填原因。源行、源 SHA、footer 摘要与阶段
见 `failure-classification.safe.json`。

在实际下载的两个 unit 中，新模块 `test_native_sh_capture_protocol_pure` 的
八个方法均逐 ID 出现 literal `ok`；原
`test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`
也各有唯一 header 和 `ok`。这是这两个 CI 样本的限定观察；不是借用本地48d
或其它 source 的结果。新8方法与原 SH 方法通过不覆盖整个 PR 的 ERROR。
该 SH 方法使用显式故障插桩，不能转述为未插桩生产 RTO 或普遍五秒恢复证明。

两份原 unit 各包含一条 `UTA_SH_CAPTURE_PROFILE`，含真实进程绑定数据。
collector 仅在私有内存校验其键、原生类型/范围和代码指纹，未调用 `/proc`、
pidfd、signal、controller 或金融路径。profile 的插桩标记为true，
`native_recovery_proven` 标记为false；source SHA 与本 C 一致。
原 ZIP、summary、worker、unittest 与完整 profile **全部留私有**，不公开
binding、birth、boot、UID、generation、nonce、DB 或候选值。没有另挑一份
无 profile 的成功 unit。公开的两个 `.finite.safe.json` 是限定字段投影，
不是原 artifact 或去掉一行后冒充的全文。

唯一成功 unit 预先选定 push3.13，artifact `14412283966`，99915B，SHA256
`ebb4c58b7387c11a4e91c1533e68860044f8864852c1b76f1a8b22aeb3747261`。
失败 PR3.10 artifact `14413235979`，89419B，SHA256
`422817544d11069b15158de58371693b13a702e0f6f86ed25d9f25e199760771`。
二者 provider length/digest 与首次实际字节一致，6成员 CRC 均过；实际
push code_commit 为 head、PR 为上述 merge，完整 source before/after maps
及 raw_log SHA 均核对，并逐 Git blob 与精确 C 字节绑定。PR 使用 C 字节
核对的依据是 API 已证明 merge tree 相同。真实 Python、platform、SQLite
元数据有限导出，原始路径及 profile 不导出。

本 C 基线是 PR35，实际 worker 是原 baseline 的精确7字段，summary 原字段
按类型和值一致。没有套用 PR42 的 W9/S9 两个诊断字段要求。资格函数没有
执行，因此所有 qualification 字段为 null；unit pass、whole CI、package
report 与完整资格分别记录。

额外只取同一成功 push3.13 job 的小 package report artifact `14412588021`，
59144B，SHA256 `e822eeb4a80182e47bfdc284fb2d0e35c78a306858b454a12e6c584ff6a38b23`。
19成员 CRC 全过，仅两个 JSON report 被语义处理；CLI stdout/stderr 内容没有
导出。报告 source 均为本 C，7checks 全true，installed8/0FAIL/0ERROR/0skip、
8命令返回0、isolatedtrue、pythonpathNone、runtime tree 与 verifier report 一致。
report 有6908个 required paths，missing/mismatched均空；45个 Git delta paths
加69个 C 内静态输入 pin 的109路径并集均被选择，runtime hash map 与 C 相符。
原始 package ZIP/report 留私有，仅有限摘要公开。这是 provider verifier /
installed report 证据，不是 collector 对 wheel/sdist 二进制的独立检查，亦
未运行 fullqualification。约51MB的 `uta-wheel-*` 是 artifact 容器，未下载。

源检查发现实际 Git delta 是45；109是与69pin闭包的物化检查并集。
首次行政派生脚本误把109当delta，在写出 SAFE 前被前置 guard 拒绝。
该 bookkeeping 失败与修正来源单列，原 artifacts 未改写、未重取、CI 未重跑。
这不是新增测试失败。API 采样使用实际 clock tool 区间，不把保存时间改作
采样时间，不声称固定30秒 cadence。

全部首次 connector、签名下载引用、原日志和 ZIP 在私有0700目录/0600文件。
失败 job 的公开日志是逐行红删派生版，receipt 绑定原 decoded UTF-8 字节数、
SHA 和删除行号；原 headers/profile 不公开，也不声称拥有 HTTP wire 原件。
其8处原非敏感行尾空白保持不变，首次格式检查 exit2；仅按 seal hash 固定的
这一份 SAFE log 精确排除后，其余新增文件检查 exit0，未为格式检查 trim
原件或 SAFE 内容，见 `format-validation.json`。
所有公开材料都经有限字段和敏感模式检查；这不构成安全审计或内核身份认证。
每个 unit 不超过2MiB，小 package 不超过1MiB，总量低于64MiB；各 artifact
只请求一次，没有重下载、替代成功样本、子 agent、对外消息或本地 target 执行。

本提交只添加 SAFE evidence/docs，未改公开 head、原 authority、marker、
workflow 或金融代码。旧 local 8.409秒、c98 NOT_RUN、8112 与 CI35/41 的原
scope/失败记录保持不变；基线没有借用 PR37 的0.1秒 cap。独立 RAW 审查
仍为 PENDING，后续由另一组单列 closure；不改写首原件。PR45 whole 仍为
FAIL，生产、真实资金、HA、10k/s 均 false。回滚本 evidence 提交不改变金融
数据；私有 first 原件和全部失败记录必须保留。
