# M04 独立单机低量诊断：具体 PREP，尚无执行许可

`next_run_permitted=false`。本候选在 D1 665e178db90dd729954e5cffa7897f9db6958132 基础上只准备 distinct04 namespace、false template 和操作计划。D1 独立 component关闭 OWN f7089d9699ca7aae905657bfe35885e4254997f2 已全 pick 为 ea05c1b4c0d3769dd47c490f6908192a4ae288af；它不批准 M04 namespace/总体执行。不能把 665e 的 158 pure PASS 移作本次 namespace 配置的执行证据。本轮未跑测试、未执行 SQL/native/owner/crypto/网络/CI，未创建 marker、04 Git ref 或 push。业务 source909、资源规则、两 argv、四流 CMS 和所有首证据不变。

## 具体候选与旧尝试隔离

新唯一候选 branch 是 `refs/heads/perf/approved-m0-20261117-04`，registration_id 为 `independent-m0-20261117-04`。controller 两常量及 once workflow 的 branch filter/job exact ref 改为04；pure source 补充 spent03 拒绝输入。dispatch workflow、D1 全函数、crypto 和 public cert 原字节不变。旧03 template 完整保留；新 [once04 false template](evidence/independent-actions-m0/once04-registration-template.json) 是严格 format2 的19字段形状，control_commit 为零值、授权 false、workspace reference 为占位。计划状态字段在 [PREP policy](evidence/independent-actions-m0/once04-policy.json)，不是可执行 marker 字段；严格 marker 禁止加入 next_run_permitted 或自由备注。

旧 M01 c71ed1756168072e0d8daea207a0d086a6dd1171 / run44169093697 首次 checkout FAILED，runtime/pure/driver SKIPPED；旧 M02 07c3dc6c3d8a6cbd239e3463b55f8904cac99340 / run44172126501 首 B UNKNOWN、P NOT_RUN；旧 M03 dfd62ae6fbbdad51b5e1b3507318b343cdc314b5 / run44179679904 首 B UNKNOWN 1.811秒、P NOT_RUN、仅3of4 cipher。上述 ref/marker/run/attempt/首 raw 不改、不删、不重建、不 rerun、不补 P。M03 precise missing path 未记录，根因未知；空流不能证明 driver 未启动。新 D1 只解释未来发生点，不回填旧因果。

所需9个历史 commit 对象均通过 Git 存在检查；接续时 sparse root 不物化 uta、31条规则，没有恢复任何全树，只追加本页的精确文档规则。源文件、原结果或审查 helper 如未物化应按固定 commit:path 用 git show 只读，不以“少文件”恢复整个 worktree。具体对象指纹与实际 materialized 必要文件见 provenance JSON。清理历史不会替代业务源码或 evidence qualification。

## root 最后授权以前的必须关闭项

1. 独立组明确关闭665e D1 publication component，审查本候选只改04命名；重新检查 source checkout step 的 literal ref 为完整40hex909和 pinned checkout action，禁止只搜索别处 SOURCE 字符串。验证04正例、03/02/01及其它 branch、attempt2、非初始创建、false/numeric approval、非 sole-parent/only-A marker负例。这些本轮 NOT_RUN，不能以 AST 检查替代纯运行结果。
2. root 选择最终固定 control commit C，重新绑定 controller/workflow/crypto/publiccert SHA；全部结果 flags 仍为 production/capacity/HA false。配置/marker hash 只是完整性，不自行授予执行许可。
3. 登记前才重新读取 workspace boot ID、hostname SHA 和带时区时间，900秒内有效；本 PREP 不启动该倒计时。实际 runner 必须证明 host/boot 都不同，记录真实硬件/OS/Python/SQLite/affinity/storage/网络配置及限制，local WAL/FULL/无 replication；未验证的 Linux/OpenSSL/硬件兼容不先声明成功。
4. runner fresh free 至少 2348810240B；normal64MiB、case32MiB、escrow96MiB、cleanup32MiB、total192MiB、额外2GiB均原值。3scan/50ms、不豁免非aux、稳定路径/尺寸下界、case56+2+2/60及postcase escrow20+2+2不变。D1 stage/public双 alias保守预留2×record，均计原cleanup。阈值是观测准入，不是物理quota或故障RPO。

## 唯一 trigger 的登记合同（下列只供未来 root 使用，本次不执行）

Root 只在具体 C 的独立审查及全部前置通过后，单独批准一次04首次新分支 push。创建 M 时以外部 `GIT_INDEX_FILE` 执行 `git read-tree C`，以完整 C tree 为基础只新增 `config/independent-m0-approved.json`；不要用 sparse checkout 当前空缺的索引重建树。M 必须 sole-parent C，diff 精确为一条 A；不得顺带修改 workflow/code/template。新 marker 采用 false template 的精确19字段，仅在 root 当次 GO 后填 actual C、fresh workspace reference、actual SHA 并设 execution_authorized=true。模板的旧零值或 false 不得自动改写成 GO。

登记后先离线逐项核 C/M/only-A/schema/hash/argv/budget，再保存 root review record。仅在 root 明确批准的那条指令中执行 `git push origin EXACT_M:refs/heads/perf/approved-m0-20261117-04` 一次；此句是计划，不是本任务执行命令。GitHub job 只认该 repo、push、exact ref、event.created=true、before=40零、attempt1；controller额外检查 deleted/forced=false、event.after/M、exact parent/only-A及代码真实 blob。workload始终另 checkout完整909。非目标 branch/event不能获得金融负载许可。

第一次 push 即消耗04，无论 checkout、诊断、资源、留存或上传何处失败。响应未知先只读查 exact ref/head/event/run，不重复 push；不得删/重建分支、rerun attempt、补另一 case或回用03。register失败但从未push的本地坏 M 也保存，但不得与 provider实际run混为一谈。当前未创建任何 M04。

一次性约束的可信边界是 root 保留 spent ref、只执行一次精确 push，加上 controller/event guards；当前没有外部持久 spent-token registry，不能声称防住有权限删除再创建04分支的 actor。该行为即使再次产生 created/attempt1 也违反操作契约，必须由 root 保留首 provider 记录识别并停止，而不是把 event.created 当作永久防重证明。该缺口是 R&D 边界，不得获得生产一次性资格。

不复用旧 marker、authority、request bundle、密钥或旧私有输出根。source909 的本地 SDK benchmark 使用 bench:sequence CID，在全新 B/P authority 内分别独立验收；这不是签名 API nonce，不能宣称全局不重复。CMS 每次调用系统 OpenSSL 新建封装，不提供 IV/nonce 参数覆写或旧 cipher 重新标 run 的路径；没有全局 IV registry 或本轮 RNG验证，不能声称统计碰撞不存在。解密严格绑定 actual C/run/attempt/case/stream，对旧 run 的 cipher 不换 binding。

## 首结果下载、封存与离线解密（尚不执行）

只读跟踪 EXACT_M 首 run/attempt1，立即保存 provider run/job/step/artifact元数据；原 log 在外部0700目录，标明是 decoded UTF8 或原ZIP来源，不打印临时签名URL、token、key/nonce。B/P所有首 FAIL/UNKNOWN、未跑 P、owner清理与实际driver是否可证均按原状态保留。成功意味着低量 component诊断完成，不意味着10k/s、30分钟、HA或生产通过；profile耗时不能当无profile容量。

下载前 root 对本 workspace 的新 disk footprint单独 fresh admission：原ZIP、bounded安全解包、offline quarantine各自计量，不能借远端预算抹掉本地旧作业reservation。按 provider artifact ID/digest下载一次原ZIP到新私有0700目录，记录 byte length/SHA/provider绑定，验证 CRC、成员数量/大小/路径、重复/绝对/父跳转/symlink及压缩展开上限；再将 manifest与safe JSON原字节、CMS ciphertext绑定核验。对任意未知字段/敏感内容先UNKNOWN不公开，不为保 raw 上传 DB/WAL/SHM/keybundle/原request/private目录。没有 artifact时明确NOT_AVAILABLE，并保存provider事实，不造ZIP或第四条流。

仅对实际 available的固定四类 driver.stdout/stderr、case-owner.stdout/stderr CMS列出私有cipher路径、length/SHA和 expected header：source909、actual C/controllerSHA、provider run/attempt、B/P、stream、public recipientSPKI、实际 capture_complete。sender origin由 provider artifact/digest/C/M链闭合；任何持public cert的人都可加密，CMS本身不证明来源。四条齐全才可 four_stream_retention_complete=true，绝不声称全部transitive/native原流已覆盖。

Root 单独用已封 publiccert与留在原私有域的 recipient key，调用当前 byte-identical `m0_stream_escrow.decrypt_authenticated(cipher, cert, key, fresh_quarantine, expected)`。本候选未读取/调用实际私钥，也没有新增 decrypt CLI。helper先严格 DER/OID/参数检查，系统OpenSSL返回0且完整container binding/length/bodySHA通过才接受；失败可能留下部分明文，fresh0700 quarantine内不parse、不公开、不以“文件存在”为成功。只输出允许的验证数值/哈希/状态；不公开 plaintext、私钥或敏感stderr。实际 Ubuntu兼容仅以后真实run可证明。

## 中止、回滚与交付门槛

push前任何失败均保PREP/no-go，根不创建 M；已创建但未push的对象可保留审计，不赋执行权。push后由原owned cleanup停止/回收所属进程，诊断/留存失败仍UNKNOWN；不回滚资金（本次只是合成数据），不动旧jobs或source909，不删除首原件。若新controller有问题，保持04 spent，停止后续native尝试，另提交最小CODE/PURE修复及新审查；切回旧 C 只是代码回滚，不能使旧失败候选或旧spent分支重新合格。

需要交付 exact C/M/firstprovider run、全部首raw、重新开存储对账/实际receipt分类及可验证留存。M04无论PASS与否均仅R&D；PR22 recovery缺陷、旧24h提前退出、生产正确性、10k/s持续30分钟、多节点/HA仍分别未过门槛。当前 next_run_permitted=false，最后一次执行授权归root具体审核，不向用户重复请求已授权的工程测试。
