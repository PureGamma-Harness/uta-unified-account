# PR62 第三源码首次 CI：独立 RAW 复核

**PASS_THIRD_SOURCE_FIRST_CI_EVIDENCE_WITH_EXPLICIT_ARCHIVE_AND_IO_LIMITS**。
复核源码 `adb36877fb6bdb91db544dabda7f0d8cbc07d26f`，采集提交
`b10452a36f268e6b5a2ef86b2f3ca95285136bd5`。本提交只追加两份 review；不改采集
SAFE、原件或旧失败。详见 [机器记录](../evidence/reviews/pr62-third-source-first-ci-independent/raw-review.json)。

首次 push44348761750、PR44348776759 均为 attempt1。封存 provider 记录显示两 run
completed/success、8 jobs 和 200 steps 全部 completed/success。8 份原始 job 摘要各为
2194 tests、0 failures、0 errors、0 skipped、worker exit0，source clean/unchanged。
这不是只依据采集者自述或只挑两个绿色样本的结果。

两个固定 Python3.13 单测 ZIP 另核完整 summary/worker/log：四份 before/after source
map 各410路径，共1640 tuple 比较，全部匹配指定 Git；worker 字段一致，lease 记录为空。
push checkout 为源码本身，PR checkout 为 `f97b2c458ea22d10c405ba8eb1068e884defabc1`。
封存 provider merge tree 与本地源码树 `e89231e65548c7f670a1a5908059f9ec802fc511`
相同，parents 为公开基线 ef7508be 和指定源码。该 merge commit 的本地对象不可用，
与 provider tree 及410映射证据分别记录；本审查没有联网补取它。

每个固定日志的原22个组件方法均有严格同一行 plain ok；新 AST negative、两个完整
guard 也逐行核到 plain ok。原恢复方法带两行交错诊断，末尾 ok，单列为 interleaved
completion。严格同一行 ok 总数分别是 push2165、PR2166，不能说2194项都属该类型。
negative 内部 callback/subcase 次数未另测量，method ok 不被扩成额外覆盖证明。

运行时66文件（65 Python+1 HTML）、1470877 bytes 及显式 V3=65 路径保持匹配。
小 package report 的66 runtime SHA 与 Git 一致，tree digest 另行重算；报告中的7836个
sdist required 路径与 Git 路径集合精确相同。后者是报告/路径检查，没有读取全部归档
内容。与上一8faa源码相比，runtime/tools/benchmarks/workflow 没有新差异。

## 原件、CRC 与有限安装报告

60份封存原件共77815633 bytes，逐件 hash/0400 及8目录0500核对通过。index SHA 为
`3f83bf1621190e7e69fa6fd5aa326f052f74702d826173d251795b5b667ca924`；580-byte
seal SHA 为 `f60178670de9ea3db98e6870d8cca9f97765c839ec1707053533d496475d6044`，
末次复读一致，公开 seal 原字节相同。14份公开 SAFE 共237423 bytes，Git、物理文件、
inventory 及对应原始字段核对一致。

3个小 ZIP 的25成员共1711948解压 bytes，逐成员完整 CRC/SHA，仅成功解码一次；
后续文本检查读取封存展开文本，重复读取另记。唯一 binary ZIP 为54775150 bytes，
外层 SHA `5b89e784363b96fb5b23e57f5a71fdcf9f1b43e2825e5b6b415fcf408b21df5f`
与 provider/原件相符。本审查全哈希一次，中央目录读取65775 bytes、2 entries；
采集者另记录其 transport/seal 两次外层哈希。中央 CRC 只属元数据，没有验证大 ZIP
成员 CRC，没有打开其 wheel/tar 成员、解压或运行未审的新 full-layer helper。

小报告中的8个 CLI test plain ok、8个 command returncode0可以记录。installed modules
仅25个名称→路径，不能冒称25个实际 content hash 或全组件功能。funding3不在该25名称
中，新 market 组件的 direct-installed functional qualification 仍开放。实际 wheel
RECORD/内容、完整 raw tar、inner artifact SHA 均未本地验证；qualification 保持
NOT_VERIFIED/null。CI 报告的 archive checks 不等于本审查验证了 binary 内层。

## 预算、行政失败和证明边界

读取新原件前冻结首计划 SHA `698438ea4282cc660f9cac25f727066829fe3b60665ada3704c9051243c09814`。
我方读账 helper 首轮混用 tuple/list，第一原件部分读取后抛 TypeError；保留该行政失败。
其精确读取量未持久记下，**actual UNKNOWN**，不写成0。continuation 在继续前按该文件
107492-byte 保守上界预扣同一层原预算，SHA
`da96cc6f2952e0f500469c5cebea81d477d659cdf226d75d45520d20568fd8c4`。

已知原件/SAFE读取82152803 bytes，加未知上界后为82260295 bytes；每层仍在原预算内，
没有提额。精确总 I/O ledger 仍 UNKNOWN，保守预算边界通过与原件/CRC检查通过分列。
缓存类型、字段位置和 `<locals>` ID 计数假设也作了行政修正，额外原件读取已记账，
不是 CI/target 重跑。该账本不证明 kernel I/O、RAM、物理落盘或目录硬配额。

独立检查36个私有绝对路径值未进入提交的 SAFE；实际 PID/nonce/绑定及交错诊断不复制。
一次缓存 schema 探查曾把标准安装路径当字符 keys 输出，故不宣称整个会话 console
零路径；未写入本提交或采集 SAFE。公开 helper 与旧版仅 SOURCE/tree 两常量 AST 不同，
但它不在 raw60 中，不能从公开副本倒推完整 executed-helper 身份证明。

provider 状态/摘要与采集者关于轮询、下载及 helper 的陈述分层记录。没有独立逐次 wall
interval，不推导 liveness、RTO 或性能；不证明未记录的全部历史调用。72dd、8faa 两个
旧失败范围保持失败，不借本次绿色改名；未读写其私有原件，PID deny10边界保持。

本审查无目标/金融 import、compile、测试、SQL、proc/PID、actor、网络或 CI 重跑。
本次仅关闭此固定源码的首次常规 CI 原始证据门槛；custom capture、完整安装资格、
pending funding、紧急队列容量、撮合/账本对账、持续万笔/30分钟、HA 和真实资金审批
仍开放。回滚仅撤回本 review，不变更金融状态，也不覆盖确认历史。
