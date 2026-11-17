# 独立 GitHub hosted runner M0 草案：未推送、未执行

本提交把源码固定的两个短诊断探针与本workspace稳定性实验隔离。工作负载另checkout exact909 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`/tree `cee60bc0b5413551030300e065d0dcaac6a7ff55`/5518个文件；控制代码、workflow和测试属于另一个明确版本，controller字节SHA由操作方批准manifest提供。本轮只写草案、读Git/官方API、执行纯stub控制测试；没有产品import、数据库打开、SQL、native编译、profile、benchmark、Actions dispatch、push或main merge。

## 本版平台阻断与已验证来源

这一版只配置workflow_dispatch，任何push/PR均不执行M0。GitHub官方文档明确：**“To trigger the workflow_dispatch event, your workflow must be in the default branch.”** 原官方Git blob、行号、长度/SHA和摘录在 `docs/evidence/independent-actions-m0/workflow-dispatch-firstparty.json`。真实default main仅有ci.yml，其事件是push/pull_request，原文件与provider blob身份保留。新文件只放测试分支不能当已注册可dispatch。不得为绕过限制自行合main或改默认分支。

根已要求下一版评估唯一专用测试分支的受控一次push触发；本版dispatch草案与37个stub结果先保留为Git历史。下一版必须另列事件设计变化、exact branch、branch-creation/before0与attempt1、root审过的immutable manifest、control/source/argv/budget绑定；当前仍没有推送许可。

3个action均使用commit SHA；read-only第一手commit API确认身份/tree，记录在official-action-pins.json。这只证明来源身份，不是action安全审计，也没有执行actions。

## 实际拓扑、机器与资源

不是单OS进程：单hosted job，两个case串行，每case一个driver加两个真实spawned owner/native子进程，共用同一实际allowed CPU（确定性选择min(affinity)）。没有把2shards改成1，没有外部exchange/REST/TLS listener。业务链是本地SDK→持久inbox→独立owner，成功订单保持OPEN，预期成交为0。

真实未来执行必须记录Linux/os-release、CPU model/count/affinity、cgroup cpu/memory/pid及rlimits、实际Python可执行文件SHA、SQLite编译参数、cc版本、本地文件系统类型/device/可用字节、接口名以及provider run/attempt/context。SQLite的WAL/FULL支持由单独受owned PID控制的短私有probe实际确认；冻结业务源码的Database路径配置WAL/FULL，但probe不是每笔历史COMMIT的硬件断电证明。没有复制或HA。

必须证明runner boot ID和hostname SHA均不同于15分钟内的workspace实际参考，且provider上下文是github-hosted/Linux、事件符合批准的触发方式、attempt1。此证据仅说明不同job/kernel/host identity与本地卷；不声称已证明物理宿主、AZ、云供应商故障域完全不同，也不是专用无噪声硬件。环境字符串不能代替独立provider run metadata复核。

只有确实另一机器才能去掉本workspace旧16.25GiB cohost reservation。该runner自己的门槛仍是 **2GiB额外安全余量+32MiB next-case+32MiB cleanup=2,214,592,512B**，在checkout后、runtime probe前、每case前和运行中以actual statvfs重测。拒绝tmpfs/ramfs/网络文件系统；f_bavail不是thin backing/hardware保证。case32MiB、aggregate64MiB包含authority DB/WAL/SHM、native TMPDIR、profile及原streams和公开记录；nofollow walk逐entry最多20000，不放松工作区门槛或删除任何原件。

## 固定工作负载与停止协议

B然后P，各一次。仅P增加--profile，均duration10/rate20/200到达/accounts100/shards2/cpu-limit1/durable-batches=true/financial-batch-size0/normal-cache-size0。载入PR20 ordered_postings为禁止；默认路径保持原样。每caseinner50s、grace2s、kill-wait2s；含源/输出处理的完整外层实测<=60s，否则UNKNOWN并不执行剩余P。job还有6分钟整体上限，超时不改成正常完成。

控制器复用exact909 `tools/run_managed_variants.py` 的owned session/pidfd/affinity握手与reap规则，不采用猜PID清理。PID/session存活后代、stream截断、resource/technical/retry/late/unknown、配置未到达真实worker或重开对账差异全部保留为首次失败并停止后续case；不能因最终terminal安全拒绝抹掉内部重试。provider rerun attempt>1拒绝，不通过重复挑快结果。允许的财务成功至少100/200，业务风险拒绝10..30；此预设诊断流量范围不是10k容量承诺。

实际提交使用readonly reopen的observed/persistent成功数和原ACK对应；元数据ACK不算财务成功。root prior三版本/8CI/新包/peer资格commit作为明确root-attested provenance记录，不冒称该runner重新执行或独立复核了那些workspace原件。M0没有撮合清算/复制，不从两个case推30分钟吞吐或生产可用。

## 安全公开证据与原raw保留边界

当前实现只生成明确白名单的JSON：机器/源hash/control来源、每case数值/延迟/结算计数、全部200个到达的计划/观察时间与原synthetic bench:CIDs、receipt状态/attempt标量。排除原receipt.payload/result、account body、key、nonce、signature、DB及private原streams。上传步骤只在public manifest逐项SHA/长度与exact文件集合校验后执行，不能glob private父目录；child环境去掉GitHub/ACTIONS tokens，只保必要系统路径/语言/动态库变量和私有TMPDIR。

cProfile原binary默认不上传。marshal记录被完整验证为function-key/call-count/time/caller的结构、EOF和尺寸/数量边界，源/stdlib/合成frozen标签有限制，完整函数与caller行导出为安全JSON；float.hex保留浮点值。该格式不含调用参数，但异常结构/未知私有标签导致UNKNOWN。父线程重叠/时钟异常保留，不说CPU百分比。原binarySHA/长度标注且明确binary未上传，不把semantic全行等同原binary逐字节归档。

**当前投影不是fullraw保存。** private原stdout/stderr/requests和DB只在runner生命周期保留，provider teardown后不承诺持久可恢复。controller/result明确这一点。原报告不许被重新标为fullraw或资格通过；M0最多R&D。root新增要求的完整递归白名单/原字节或最小加密stream保留方案见retention-options.json。该方案仍设计，未做任何keygen/openssl执行或dispatch。

静态真实stdout是源main输出的完整summary JSON；健康空stderr可原字节保留，但要先给完整summary每个顶层/递归分支做字段/类型/来源校验、确认stdout与summary文件原字节相等，而不能仅数值投影后说fullraw。当前代码只实现投影，没有声称已完成全summary递归审计。未知/可能敏感stderr绝不可直接公开；只记录UNKNOWN并保留私有。若root要求跨provider teardown完整原stream，需先实现并独立验收加密escrow方案。

## 可复核结果与后续门槛

第一轮35 pure stub tests PASS；新增attempt1与合法frozen profile标签后37 tests PASS。两轮原cmd/cwd/UTC/outer-monotonic/代码SHA/stdoutstderr分别保留，均0SQL/product/native/profile/Actions执行。这些测试只验证控制分支、拒绝和数值投影，不能代替真实runner的owned进程、WAL/磁盘、编译、对账和隐私验收。

后续须先独立review actual controller/workflow/retention策略与平台触发方案，再绑定root-approved具体控制版本及source909、argv、budgets/once范围，才能批准一次新runner试验。当前文件默认PREP、不push、不dispatch、不main merge。回滚是停用/删除未启用的专用workflow分支，保留所有已确认原始证据；不改909、old24或其它financial authority。
