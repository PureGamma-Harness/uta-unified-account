# Cross MM 首 CI 与描述符纯算：独立原件复核

结论：**EVIDENCE_BINDING_PASS_WITH_EXPLICIT_SCOPE**。只读审查
6b2cdce7a2c7dcc25bdd54f45ffe322e15e9c4c5；原始 CI 仍全部失败，
新描述符纯算在其限定范围内通过。修复后的正常 CI 尚未运行。

## 新纯算的实际证据

代码为 b4e1b5907e6b64578d39614f87c866d7f4f65631，
先前独立 CODE 审查为 568d8c3e56a3ad5ac88ddabb690a8f6c02308c0f。
新计划 SHA-256 为
021639834b185c8e944d180919d082e5301d6d6b0d0397b2e49f036961d39416。
九项输入共170187字节，物理常规文件、冻结 Git 和保存的长度/SHA、前后 stat
一致；计划物理字节也相同。两个真实只读 property 节点仍保留，
六个测试方法的 AST 与首次公开源码相同，修复仅初始化 backing fields 并检验
getter 身份与赋值拒绝，没有为测试添加 setter。

八份调用方/driver 原件共13901字节，与公开副本逐字节一致。
driver stdout2014字节、stderr1112字节：六个方法各有实际 ok，
BEGIN/END、execution receipt、计划中的15个有序 completion ID 精确对应，
0 failures/errors/skips。ID 是受信任夹具在断言后记录的完成项，
不等于15个独立测试进程或独立证明器。END 前原始输出1651字节，
全部输出3126字节，低于共享256KiB减512字节 trailer 的上限。

记录的运行时是 Python3.12.14、CPU affinity [1]、-I -S -B、
二进制 SHA fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7。
内层75972194ns；调用方另记229264668ns、实际 exit0/reaped、
双 prefix EOF、空 prefix streams、未强制清理。完整 argv 包含
timeout --signal=KILL 10s。这些层次分别核对，没有用内层 END 代替外层退出。

调用方独立程序源码没有归档；依据是保存的 root exec input5937cf、
argv/intent 和 actual receipt，而非冻结的 standalone controller capsule、
远程认证或本次重新探测的内核历史。调用方单独保存 end_monotonic_ns 和 elapsed，
没有另存 start_monotonic_ns。旧省略 property 的抽取类纯算仍保留原范围，
不能据此声称正常 unittest fixture 兼容。

## 首次 CI 仍为红色

首次源码 fc2d574d7ac434a214bf332649edf0d2effc2a8c：
push44275550971、PR44275682105 的八个 job 均 failure。
八份已存 decoded job summary 各2055 tests、4 errors、0 skips、worker exit1；
PR3.12另有1 failure，其余七份为0 failures。attempt1 是已保存的收集标签；
job response 没有原生 run_attempt 字段，本次没有额外查询提供方。

只下载过的两份 unit ZIP 为 push3.12/14414781552（99833字节）
与 PR3.12/14414244607（101681字节）。各3成员 CRC 通过，
解压原文与私有成员副本相同；各368项源码映射前后相等且逐项对应首次源码。
legacy worker 七字段的原生类型和值均与 summary 精确相同，
不能以 false 值或错误数忽略失败。

两份完整 unittest 原件各有四个相同 ERROR，均在真实 service 的只读
product_catalog 上赋值触发 AttributeError。四个新测试 ERROR、另两个新测试
ok 的逐项记录及仓库栈帧均核对到首次 Git 源码。其它六份完整 unit artifact
未下载；对其结论限于已经保存的 job summary 数字，不扩展为逐栈复核。

PR3.12 的额外 SH FAIL 在 test_durable_faults.py:1456：
undo 后原 capture horizon 内仍未离开 SH。该断言在五秒恢复检查前，
不能写成五秒恢复失败，更不能确定锁持有者、并发时序或与描述符 ERROR 同因。
其原因继续为 **UNDETERMINED**。

已保存提供方 merge87792e6d 的 parents 为 base9b61e5f 与 headfc2d574d，
tree ee9ec1b743ec09cce252013a5eaaef9ec3df316f 等于本地 head Git tree。
这依据保存的 provider commit payload、PR 关联及 head 源码，
没有声称本地存在该 merge commit 对象或重新取过 checkout 日志。

有一处原文措辞差异须保留：原交付文档称“no successful package step”，
但八份 job metadata 的 “Preserve exact package and installed validation evidence”
步骤均为 success。实际 build wheel、build/verify、installed-package verification
均 skipped，已存 artifact 列表只有 unit，没有成功 package artifact，
qualification 为 null。证据保留步的 success 不等于构建或安装验收通过。

## 保存与限制

私有24原件1431017字节与 PRIVATE-SEAL、公开有限 inventory 逐字节/长度/SHA
匹配；根目录0700、文件0600、读取期间状态稳定。signed-reference 文件只读字节
计算哈希，没有解析、打印或复制值。14项新增 SAFE 文件物理字节与 Git 相同，
有限六类 credential/auth/private-key/signed-query/UUID/32hex 检查均为零。
所有完整 CI ZIP、unit/job 原文和 connector 引用继续留私有；
本审查只新增报告、有限 JSON 和清单，不复制它们。

收集阶段的 E2BIG 在命令创建前拒绝，以及 normalized-result JSON 解析错误，
保留为行政收集错误；没有把它们当 CI 错误或实际 target 尝试。
本审查自身的 reader 字段形状/事件名/步骤语义假设修正也不改变任何原结果。

首次源码到描述符修复的61个 uta Python 文件及 dashboard 逐字节无差异；
原三库 SQL 证据不在这四项修复差异中，本次没有读取数据库或重跑 SQL。
完整 admission/fill、normal-module CI、真实资金、持久化恢复、容量、HA
及平台生产验收均未由此闭合。

本次仅 Git、文本、严格有限 JSON、AST、ZIP CRC 和
NOFOLLOW/NOATIME 稳定字节读取。没有目标 import/compile/test、SQL、进程/PID
探测、signal、网络/API/下载或目标 child。没有修改首 CI、旧纯算或新首原件。
回滚本报告不改变资金状态；不得删除红色证据或把新纯算改写成旧 CI 通过。
