# PR46 修正源码的首次 CI 证据

采集对象是修正源码44d6273a23dbea0745a38050022d6a071539967c，
base9b61e5f35dd2196ef2fdddfa03559eca3f1322ec。其首次 push44281078769 和
PR44281092043 均 completed/success、原生 run_attempt1；八个 Python3.10–3.13
job 均 success。终态只读取一次，没有轮询、CI retry、rerun 或本地目标执行。

**这是新源码的首次 CI，不是把旧源码 fc2d574d 的失败重跑成绿色。**
旧首轮八个失败 job、每份四个 property ERROR、PR3.12 的额外 SH undo
capture failure 及其原因 UNDETERMINED 均保留。先前省略 descriptor 的纯算、
后来六方法 descriptor-aware 纯算与本次正常 CI 分别保存，不互相替代。

## 本次实际保存范围

只有以下三个 artifact 被请求并下载，各一次：

| 来源 | Artifact ID | ZIP 字节 | SHA-256 | CRC 成员 |
| --- | ---: | ---: | --- | ---: |
| push3.12 unit | 14417342557 | 99208 | 535fc1091dea447090d014f9f5496331573ec85a295a2ade42a922d37da5489c | 3 |
| PR3.12 unit | 14416394006 | 99125 | d727df4f88d6c442d51a923eed3e621b801b286725c5e1813f8f72b906d04851 | 3 |
| push3.12 package report | 14417921538 | 59452 | 9d5e7bcc37de144db424cd8ebcef2cb4c1d03f3af4dd37dbd376bef355ce9095 | 19 |

其余六份完整 unit、其它 package report、任何 job log，以及约51MB的
wheel/sdist artifact 容器均未获取。八个整轮 job 的结论来自提供方 metadata，
只有所选两份 unit 的原文经过本组逐项核对，不能声称已审八份完整单元日志。

私有目录 /workspace/pr46-corrected-ci-private 保存51个原件/收集回执，
共3055357字节，另存 PRIVATE-SEAL；所有目录0700、文件0600。
所有 ZIP、25个成员原文、HTTP headers、connector 下载引用及可能的
profile binding 一律私有。公开只保存有限字段投影和 opaque 字节清单，
不公开原 archive、原 stdout、原 header 或 signed reference。
每份 unit 上限2MiB、小 report 上限1MiB、总额64MiB，实际均未超限。

## 正常单元测试与源码绑定

两份实际 unit 各2055 tests、0 failures/errors/skips/expected failures/
unexpected successes、worker exit0。六个 cross-maintenance 方法各有一次正常
unittest 的 ok；原 SH capture/recovery 方法也各有一条 ok。
legacy worker 的七个字段与 summary 逐原生类型和值相同，
其 unittest_passed 为 true。本结果独立于本地 selected-AST pure PASS。

两份实际运行时均为 Python3.12.16
(main, Oct 26 2026, 02:48:44) [GCC15.2.0]、SQLite3.46.1，
不借用本地纯算的 Python3.12.14 运行时。
unit 原文 SHA、summary/worker 副本、ZIP成员 CRC 全部对应；
各368项 source_sha256 与 source_sha256_after 相同，并逐项核对本次 C 的 Git 字节。

实际 PR unit summary 的 code_commit 是
acf65de83d206418120b72f7eea6a38a0cc87d3e；
保存的 provider merge object 的 parents 正是 base9b61e5f 与 head44d6273，
tree3c86a2bc83fda5630b32d130950edea330eac294 等于 head Git tree。
这项关联依据保存的 run/PR/merge metadata 和 PR unit 源码映射；
没有另取 checkout job 原文或重新查询过去的进程。

## Package report 的有限结论

所选19成员小 report 中，archive manifest 的7项检查均 true，
installed report 为8个测试、0 failures/errors/skips，8条 CLI 命令 returncode0；
安装测试原文含8条实际 ok。报告 source_commit 都是本次 C，
helper SHA 也对应其 tests/test_durable_cli.py。

6936项 required_files 无缺失、无重复，集合精确等于 C 的全部 tracked files。
报告62项 runtime（61个 Python 文件和 dashboard）逐项 SHA 与 C 相同，
canonical runtime map 的摘要与安装报告一致。
原首次源码 fc2d574d 到 C 的 uta runtime 差异为零，
当前 fixture 与独立审查过的 b4e1b590 字节相同，计划 SHA 仍为
021639834b185c8e944d180919d082e5301d6d6b0d0397b2e49f036961d39416。

这是**报告及其源码绑定**的核对。本组没有下载或重新验证实际 wheel/sdist
二进制，也没有在本地 build/install/运行 CLI；报告中的两个 binary 摘要
仅作报告间关联。完整 qualification 没有调用，记录为 null，不能写成通过。
原三数据库 SQL 结果没有重跑或由本次重新认证。

## 原件、隐私与复核

六类有限公开检查为零：credential assignment、未掩码 Authorization、
private-key block、signed query、UUID、独立32hex候选。
这只是对新增 SAFE 投影的定向检查，不是全仓库安全审计。

首次保存完整 PR connector 时，单个 exec 参数过长被执行服务在建进程前拒绝；
随后只把已经缓存的同一返回值分块保存，没有重新调用 API。
一次 JS TextEncoder 不可用的元数据统计错误也保存为收集错误，
没有目标执行或 CI 影响。全部原始 connector/transfer 结果保留，不回写历史。

本次执行11次只读 API 获取（含三个指定 artifact 的引用）及其3次一次性文件传输，
没有获取 headers API、额外 job log、密钥、原 authority、数据库或大容器。
只做 JSON/文本/CRC/Git/稳定字节解析；未 import/compile/test 目标，
未运行 SQL、PID/proc 探测、benchmark、signal 或目标 child。

独立 RAW 复核状态为 PENDING；后续由另一工作组核对本提交与私有原件。
本提交只增加 docs/evidence，不改 CODE、测试或原首轮证据。
撤回这些证据文件不改变任何资金、仓位或日志状态；应保留私有原件及首红结果，
通过后续新提交修订解释，不覆写首次记录。
生产、真实资金、持续容量、HA、完整 UTA/PM 平台验收均未由本次 CI 宣告通过。
