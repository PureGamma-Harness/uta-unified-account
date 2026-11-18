# M05 控制面整合：d58 首次 PURE 已通过，实际 M05 未授权

**最新状态，supersedes 下方 a365 PREVIEW：**固定 source `d58e2445a851c11c9cb7f06eebd0cf496da1d268` 的首次 combined 已执行并通过：九模块219 tests、0 failures/errors/skips、exit0，CPU2，1.360591174秒；恰六个 guarded 标准Python child全部exit0/reaped，two-negative/four-positive proof闭合。首原件封存于 `027fc1b7180d2b868dd0817c670cda871417c865`，独立只读artifact review已CLOSED/PASS，仅适用于source-bound guarded PURE。详见 `m05-d58-first-combined.md` 和当前policy。

实际M05尚无GO：`execution_authorized=false`、`next_run_permitted=false`；只有root授权的本地C/M候选准备及只读ref核对，没有push/dispatch/实际SQL、业务、worker、OpenSSL或网络probe。原4e首次4PASS+8ImportERROR/0child/exit1和G首次28case纯桩/AST结果完整保留，均不被新通过覆盖。下方所有“尚未执行combined”“NOT_RUN”“review pending”均为a365当时的历史快照，已被上述最新事实supersede，不描述当前执行事实，也不构成实际M05权限。

**a365历史记录：**本树基于6010e920a168b35fccfc9ef9ee34e030b28b11d9，保留其已交付ff814业务runtime；当时只整合M0控制、测试、公共打包选择和证据，尚未执行combined PURE、导入业务/控制模块、SQL/native/crypto/网络/CI、创建M05 marker或触发ref、push。原 `policy-first-pending.json`、原 static 首记录及下文均保留原阶段含义，component旧结果不转移成新树通过记录。

## 来源与安全合并边界

冷导入87c9675及独立173accf完整整合；其四真实-I-S原child只验证当时8cc/89f source，后续独立六parent纯桩关闭strictgate，没有重跑原8。包装8735668289ff739894b0318d391ce5409b7e6df4带入actual f3a source七检查及peer0c1808；不代表当前6010/05树已build。FS采用最终3cc254db1d59f805a6d64825d75360a7f31aad41/code4f316a89da1a001a9670a41cfeca754e67de1401，不把旧c524的19PASS1RED宣称通过；须另有固定独立token/proof关闭证据，当前状态以policy版本记录。

M04安全首结果69d2全merge。general CI首证据dc9e42ababfd29106129d85ecd00ae4c38ebbb8c仅cherry-pick两份docs/evidence，不merge其actualMe643父链。最终tree不得含config/independent-m0-approved.json，且909以来祖先marker路径变更必须为空；source string引用旧M/CI不是执行授权。M01–M04所有首FAIL/UNKNOWN、未跑P、原判型/证据缺口均保留。

已核6010与ff814的uta subtree同为4a0d5a989f0d7112454e41bbdb0162ffef34dbe4，本整合对6010的uta为零diff。除授权MANIFEST三条精确public选择外，6010既有文件不变；新增M0资产不改业务源。没有物化uta或完整repo，仅必要M0 code/tests、公共cert metadata和本PREP文档。后续PR基PR25，不把本PREP当作新的业务版本。

## 05新身份与不变的业务矩阵

仅把controller APPROVED_BRANCH/REGISTRATION_ID、once workflow两branch literal改为refs/heads/perf/approved-m0-20261117-05 / independent-m0-20261117-05，并补spent04负控。04实际已spent，旧模板/marker/root运行原件不改。当前false模板为严格format2/19字段：execution_authorized=false、control_commit零值、fresh workspace引用未采样；next_run_permitted只在外层policy中，禁止塞进strict marker冒充新schema。

control树携带6010业务runtime与WORKLOAD分开：实际候选仍须另checkout完整909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0/tree cee60bc0b5413551030300e065d0dcaac6a7ff55，TRACKED5518，不能悄悄换成本control树或6010工作负载。B/P固定顺序、10秒×20rate、100accounts、2shards、1CPU、durable_batches、financial_batch_size0、normal_cache_size0，P仅加profile。仍需真实持久接纳/预占与receipt分类，profile不是speedup arm。

3scan/50ms原重试clock、parent/main/未知路径/symlink/权限/EIO拒绝、类型provenance及fresh-scan token单次消费保持组件代码，不放宽catalogue。normal64/case32/escrow96/cleanup32/total192MiB、额外2GiB、MIN_FREE2348810240B、case56+2+2/60及escrow20+2+2不变。父/主库devino身份替换不足仍是单列未实施提案。四条closed streams、CMS严格AuthEnvelopedData/AES256GCM/OAEP-SHA256+MGF1SHA256、recipient public pins不变；完整raw不等于公开DB/key/request/private目录。

## 测试入口的实际可达性

两workflow都补cold helper/test和FS entry_types/scan_proof的精确sparse路径。原实际command `python -m unittest discover -s control/tests -p 'test_independent_m0_*.py' -v` 匹配本树全部九个M0测试文件；没有泛化到全tests目录或导入业务。静态manifest列每个test、相应sourcehash、实际两command和checkout唯一workload step完整40hex/action pin。静态匹配不等于执行成功。

本轮combined PURE严格NOT_RUN。待全部component源码固定、token/proof独立CODE关闭，root才可另给一次新source整合纯套件的具体预算/命令；实际child/真实crypto等能力若未授权仍不执行。一般CI四runtime、包装和native恢复需各自新source验收，不重跑旧源来洗首FAIL。-I/-S仅是导入契约，非网络/OS sandbox，与H1 AuthDB probe隔离。

后续预算必须点明cold-import依赖：原两个断言各启动1个受guard的新解释器，新cold测试另有4个真实小解释器，预计共6次标准Python child；其余timeout/reap/OSerror是纯桩。这不是零process测试，也不是financial/native owner或真实OpenSSL/SQLite，不能把root对CODE/AST的本轮许可当作这6次执行许可。实际数量与全部首结果须由新的combined source测量，不用旧4child proof替代。

## 最后登记、故障与回滚

只有fixed C的独立namespace/policy/源码审和root明确的后续新tree验收通过，才讨论actual M05。root登记前fresh读取原workspace host/boot/time（900秒窗口）和资源，证明hostedjob host/boot不同且local WAL/FULL/无replication，实际硬件/OS/Python/SQLite/OpenSSL由实际runner记录。不用旧03/04 false模板或checksum替代GO，不向用户重复索要已授权工程测试确认。

root具体M只能是C唯一parent、完整temp GIT_INDEX_FILE read-tree C后仅A config/independent-m0-approved.json，strict19字段/实际SHA/原argv预算闭合。先封本地M审核原件，最后一次exact M:refs/heads/perf/approved-m0-20261117-05首次新ref push。响应未知只读查exactref/run，禁止再push/delete/recreate/rerun/补P。第一次push即消耗05；当前没有外部持久spent-token registry，一次性边界仍依赖root保留ref和首provider记录，不能称生产不可重放令牌。

执行如获另行GO，只跟踪exactM首run/attempt1，保首provider/log/ZIP/digest/CRC/manifest，任何UNKNOWN即停止后P。root实际offline decrypt仅对available CMS，先strict DER再系统OpenSSL0及container/source/C/run/attempt/case/stream/len/SHA绑定，失败明文留fresh private quarantine，不能以输出文件存在认成功，不补造第四流。receiver encryption不证明sender，origin由providerC/M/digest链闭合。本轮没有读取root实际私钥或任何plaintext。

回滚仅退回本PREP/组件CODE并保全部首证据；不得改旧作业、clock、600grace或runtime6010，不重启任何任务，不把spent注册重新激活。跨component冲突或独立RED时继续NO_GO，先最小修复再新source验收。所有生产、10k/s×30min、HA及真实资金启用flags均false。
