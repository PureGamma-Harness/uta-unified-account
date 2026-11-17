# M02首失败：限定SQLite sidecar瞬态重新枚举（CODE/PURE候选）

M02实际marker `07c3dc6c3d8a6cbd239e3463b55f8904cac99340` 的parent为e466b67，run44172126501/attempt1/job134353729679首次FAIL保持原状态，不rerun、不删除重建02。源码checkout、Python设置和114项pure控制成功；controller execute失败，public manifest核验与artifact上传成功。ZIP artifact14366519733大小228,850字节，实际SHA256与provider digest同为 `1ae12dfbdb8f7798b6579de4d6988bb0628a481320f7d7e04e98b000d3f290d4`，CRC通过。11个public records及manifest原字节、原source5518映射、provider状态与四cipher绑定由独立OWN278191完整保留；该OWN与此前41ced分别pick为74ec6ef、8c749dc。

实际停止为case B约1,173,100,276ns，owner2606/birth9324在resource health检查触发UNKNOWN并TERM(-15)/reaped，原因为已枚举 `B/workload/authority/shard-0000.sqlite3-shm` 后lstat ENOENT；P明确NOT_RUN。public report没有actual_driver_pid，不能据此宣称金融driver未启动，也不能将UNKNOWN改称业务金融失败。发生了WAL/FULL探针与B的启动流程，但没有通过的持久接纳/交易/容量成绩。

实际Ubuntu OpenSSL3.0.13严格CMS协议capability通过，Python3.12.14/SQLite3.45.1的journal_mode=wal、synchronous=2通过。四条已关闭流密文均保留，root独立认证解密第一次通过，实际四stream均0字节；作者未读取actualroot私钥或未认证明文。空输出不证明没有SQLite初始化或没有金融动作。root公开观察SHA `9305ed86655f66004cddf83ad4721d4d44a88070baf15d2da5d1cb1c69dcb9e6` 已在独立证据中保留。provider原decoded UTF8 job log为62,473字节、SHA `79aeec366fc369cebc210c707058b0684e864b682f0180927978ad571aa1f66a`，完整log/ZIP/cipher继续私有，不将其称raw log ZIP。下载connector的一次调试输出误包含临时URL，已向root记录边界，URL不入Git、不复述；后续只投影安全字段。

## 严格修复规则

此候选只修新的M0 controller，不改source909、ledger/native、现有jobs或旧存储。资源枚举改用nofollow lstat及显式传播os.walk错误；private聚合与case tree两条路径共享限定的fresh scan准入。

仅private `[B|P]/workload/authority/shard-NNNN.sqlite3-(wal|shm)` 及 `runtime-probe/private.sqlite3-(wal|shm)` 已被枚举后lstat ENOENT可以重启完整扫描。case子树计量也只允许同一严格相对路径。public/未知路径、目录消失、稳定main缺失、parent或main为symlink/非对应类型、permission/EIO均不进入恢复。先逐级nofollow复核root/parents为目录、对应main为regular；不把任意ENOENT略过，不沿用半次计数。存活sidecar正常计量。

每次调用最多3轮，50,000,000ns cooperative retry边界从该调用首次扫描开始；重试准入与完成都核相同deadline，不重置金融case56+2+2/完整≤60秒预算，也不额外sleep。每调用保存已见非aux稳定路径与类型，重扫必须仍看见它们且类型不变；regular尺寸按本调用已见max保守计量，不丢前轮partial观测下界。合法aux可以消失，存活aux照常计量。持续churn、过预算仍UNKNOWN。计量是非原子保守观测，不保证物理磁盘配额或中断阻塞syscall；可能因短时旧max或稳定文件合法rename而保守UNKNOWN。任一已观察normal64MiB、escrow96MiB、cleanup32MiB、total192MiB超限立即拒绝，不可通过重试丢掉超额观察；case树也保32MiB检查。内核/资金决策没有cache或验证弱化。

新增17项纯metadata/file回归覆盖aggregate/case aux消失、runtime-probe、稳定main/未知名/权限/父目录/symlink拒绝、连续churn3轮、50ms重试准入和完成超界、重新枚举新增增长仍触发cap、前轮已见稳定路径/类型不得丢失和partial尺寸下界保留。合并131项pure通过。测试只创建内容为synthetic的普通文件名，不import sqlite或运行金融/native。首fixture曾用bound-method mock导致TypeError，其源与原first失败保留；只修mock绑定后旧controller真实FNF反例保留。合并套件中旧61秒超时测试假设固定3次monotonic调用，新增资源计时使其StopIteration；改为按owner阶段推进假时钟，仍测61秒必须UNKNOWN/quarantine，原失败不覆盖。

## 相关但独立的风险与下一提案

旧24h887在20:27因authority.sqlite3-shm ENOENT提前终止，root保留82,258.607853086秒/20,560 of21,600/exit2证据，独立OWN e0d005c。旧案无原stack，不能由同文件后缀宣称唯一同根。managed_observer另审source909/887和输出observer临时JSON race，候选7065719的白名单是`.observer-*.tmp`，与这里SQLiteaux不同；不互cherry运行时、不热补现有909。这里不允许observer tmp或其它临时名借用SQLite规则。

为准备未来distinct提案，控制policy/默认false模板命名03（`perf/approved-m0-20261117-03` / `independent-m0-20261117-03`），原01/02明确拒复用。format2、V2容量、业务argv、source909和CMS/publicrecipient保持原值；新的sha/hash仍须root与独立组审。只有外部PROPOSED JSON准备，没有M03、literal分支、push或dispatch授权。新的native/SQL/crypto实测全部未运行。

原M01源码checkout失败、M02资源检查UNKNOWN、PR22 stopped-owner恢复ERROR、旧24h提前退出均不被本纯组件通过覆盖。production、10k/s×30min、HA、可靠性放行全部false/NO_GO；即使未来批准低量R&D，也没有交易所生产验收资格。回滚为不登记不推新M，保留所有首失败与旧run，源与运行任务不动。
