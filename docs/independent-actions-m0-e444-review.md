# 独立审查：e44493f M0 控制器暂不通过

**审查结论：NO_GO。** 控制提交固定为 `e44493f67846adbdee0ff1064743cd1444c5cb4e`，controller SHA-256 为 `4e3298532c8b40733d74f116eb06a3ab58d110cdac2d01bc27e9db59d97e37ad`，once workflow SHA-256 为 `c2c1652015c6a3ee4800436588d312478a195dad2d5eb698856d08892dbf6b3b`。作者的49项纯控制测试不能覆盖本次发现的八个实际纯反例。此结论针对证据接纳控制，不是认定源909已产生错误交易或这些矛盾真实出现在生产。

仅使用不可变 Git 文件、AST、合成 JSON/gzip 与纯 parser 调用。没有导入 `uta` 或 `sqlite3`、启动负载/原生 owner、SQL、profile、Actions、dispatch、push、创建实际 M/授权登记或修改作者文件。读取 Git blobs 使用了两个普通 Git 子进程；随后 controller 的全部 subprocess 入口被禁止。没有声称整个审查进程完全没有 OS 子进程。

## 实际纯反例与首错

review helper 首次错误地把 Git cwd 定位到 `/workspace`，在读取 controller 前失败；原 `first-pure.stderr.txt` 与空 stdout 保留。只修 helper 的一行路径后，第二次在 CPU3 于 `18:42:19.342162` 至 `18:42:19.460382 UTC` 完成，monotonic 耗时118,223,779ns。controller 原字节与输入不变，两个一致性正例接受，八项应拒反例均被接受，helper按设计 exit1。原首RED保存在 `second-pure.stdout.json`，未改为通过。

基准采用作者纯 shape fixture，经独立合成200行配成160成功、20业务拒绝、20控制拒绝，固定10秒；请求全部是合成 `bench:<sequence>`，不含客户或私有数据。独立变异和算术均在 reviewer helper 中实现，没有复用生产风险函数。

| 问题 | 原 e444 接纳的矛盾 |
| --- | --- |
| summary计数 | outcomes为159笔成功、counts/reopen为160笔，仍接纳 |
| 时间分母 | 固定10秒计划却 elapsed=-1，仍接纳 |
| 吞吐算术 | 160笔/10秒却声明9999笔/秒，仍接纳 |
| 延迟分位 | 同一总体P50=100、P95=1，仍接纳 |
| 原业务引用 | `bench:2` 成功行携带 `bench:199` receipt，仍接纳 |
| 成交义务状态 | `financial_succeeded` 对应 REJECTED receipt，仍接纳 |
| 时间戳算术 | latency=1ns但实际差1ms，ACK早于开始，仍接纳 |
| 全量总体连接 | summary160成功而完整200行只有159成功，两个投影各自接受，main后续不连接 |

对应固定源码为 `project_summary` 第267–315行、`project_arrivals` 第317–336行和 main 的分离调用。至少应按完整200行重算分类/ACK/成功/拒绝/late、校验receipt原CID与状态、时间戳关系、分母/速率/分位，且与summary、重开核对结果连接。任何不一致应为UNKNOWN/拒绝，并保首证据；不能依赖输入中的 `probe_qualification.passed=true` 代替这些检查。

这些反例是合成 parser 证据，并非真实 CLI 或真实金融执行复现。它们证明当前独立接纳边界可接受矛盾输入；源909的已有真实性核对不能替代此接纳层的独立约束。

## 控制授权与退出边界

以下为固定源码审阅结果，未通过实际 M、远端 Actions 或原生故障试验验证：

- 新 workflow 只监听 literal `perf/approved-m0-20261117-once`，job限制 created/before0/attempt1；controller再核 forced/deleted/event/after。登记 M 仅允许单parent C和唯一新增 `config/independent-m0-approved.json`，C..M不能改变controller/workflow。C、M、source909分别checkout；controller与workflow字节摘要绑定，argv/budget按类型敏感canonical JSON比对，避免self-SHA循环。
- 原 dispatch 文件与a28原件逐字节相同；官方 `github/docs` 证据明确 workflow_dispatch 文件必须已在default branch。新push方案解决登记前置，不需要或授权main合并。
- 真正授权来自root对具体C/M的明确审阅和一次push。manifest的布尔值和checksum本身不是权限证明。恶意仓库管理员不在此控制威胁模型内；删除重建分支和跨registration全局防重没有已实现的持久registry，文档已明确，不能称一般分布式exactly-once。
- `source909:tools/run_managed_variants.py:472` 的 owned runner 有 unreaped leader/pidfd、session/birth检查、launcher affinity ACK、只信号自身组、TERM→KILL与reap。controller首UNKNOWN停止P。这里只审了源码，未取得真实远端cleanup、OS调度或硬件证据。
- B/P各有1 driver与2真实owner，不是整个job只有一个OS进程。此外controller还包含独立的SQLite元数据probe子进程：10秒watchdog、2秒grace、2秒kill、64KiB输出；它同样必须包含在任何后续具体GO范围内。本次没有执行该probe。

## 资源与 parser 边界

独立hosted环境、fresh workspace boot/hostname不同、Linux本地文件系统、实测WAL/FULL、同allowed CPU和2,214,592,512字节fresh free均是运行时待验证前置。GitHub hosted上下文和boot/hostname差异不是物理宿主、AZ隔离或HA证明。case32MiB/aggregate64MiB是周期检查阈值，不是OS硬quota；sourcecheckout和其他步骤已占用的磁盘需在fresh free中实际体现。不会动用本机原16.25GiB预留。

另一个静态缺口：第318行先 `gzip.decompress` 完整展开，再检查8MiB，无法在展开前保证内存界。建议以最多8MiB+1、200+1行和单行上限的流式处理拒绝超限；未做OOM试验。wholecase60秒在解析/发布完成后才检查，不等于该阶段有独立硬watchdog。原生负载的50+2+2与job6分钟是不同阶段的边界，不能合并为已验证的端到端硬上界。

## stdout与隐私保留的实际含义

源909 `benchmarks/run_managed_benchmark.py` 第819行写summary，main第854行将完整result JSON打印到stdout。完整summary包括startup/fence、final diagnostics、feed/error、affected_commands和profile等分支。异常时原stderr可能包含详细私有上下文；不能按任意文本或repr公开。

当前C读取summary文件，输出受限scalar/arrival/profile-semantic投影；没有验证stdout与summary原字节相同，也没有对完整summary所有分支执行已审的递归schema。`verify_public`检查文件名、类型、大小、摘要和集合，不是每种payload的完整递归隐私证明。因此它不能等价为“所有原始stdout/stderr已安全完整持久保留”。

当前root登记唯一允许的 `safe_projection_private_ephemeral_R&D_only` 与实现一致。private streams仅存在于runner生命周期，provider teardown后没有durable escrow。首UNKNOWN可以公开保留有界分类，但无法据此恢复未上传原异常stream；不能据未知失败完成原始证据验收。

Option A的完整递归白名单+原safe bytes和Option B的仅stdout/stderr CMS认证加密均仍是设计。没有keygen、recipient验证、tamper验证或加密实现。即使八个算术反例修复，本模式仍只能作为root另行批准的R&D诊断；完整raw、性能验收、生产RPO/HA与真实资金均不得承接。若要求跨runner保存所有首失败stream，须先具体实现并独立验收相应retention方案。

## 修复复核与交付

作者和root已收到首RED。review没有自动修作者文件。下一控制revision须保留e444和本次首错/首RED，使用新固定SHA逐项证明八反例拒绝、一致正例通过，并说明流式解析/完整population连接及retention范围。真实M、push/dispatch、原生负载只有root另行具体最终GO后才可能执行；本审查不授予执行权。

该提交只新增独立review脚本、合成证据和文档，无运行时/API/数据库迁移或部署。撤销review提交即可回滚工作树；不能删除首失败、旧C/dispatch、源909或原实验记录。所有source/controller/workflow/firstparty输入与证据文件SHA记录在 `review-manifest.json`。
