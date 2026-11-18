# 首次资金费三方法 SQL：SAFE 证据候选

源码 `2326106b3bf8cf6d2713e4cf8c7926afdf6962ab`，plan
`fb3d1fb820f3cf4112699615a0a8ae05bae82ec945ac1c7d858a2c92fed7f241`。
独立修正CODE审查e29d2b76闭合、root另给完整唯一argv后首轮执行一次，无预热/重试。
本目录待原独立组RAW复核，不表示生产或完整金融验收。旧d668 finding/NOT_RUN、
f341全六方法计划、49407/d7e0历史字节均保留，不改写历史。

原固定三条SQL方法与一次明确声明distress待成交RO设置完成；0 failure/error/skip/EF/US。
五库新RO快照核对实际6 matches/12 paired fills/32 journal/3 committed periods。
故意orphan库资金费核对按预期以funding_reconciliation拒绝；不能称五库全部健康。
冻结控制内的人工oracle断言已通过，包括真实treasury存款资本转移、幂等冲突、
负现金不作本金、实际撤旧RO/新-1@100只减仓计划、schema/artifact、账本与撮合对应。
本证据不补查任何DB；这里只发布已有回执的有限结果，没有对失败补查询或再运行。

实际67pins/1,412,889B相同，Py3.12.14/exeFA674/CPU1/-I-S-B。128个测试阶段handle
在重开前已闭合；5个RO重开后累计133个handle全部已闭，无泄漏清理。
观察144次，峰值及最终DB逻辑1,994,752B/15文件；每文件RLIMIT4MiB。
80MiB是已声明源码/文件族边界，不是硬总quota，观察不是连续native写监控。

caller实际outer exit0/wait+reap/双EOF、完整launcher raw0B；owned host亦exit0/reaped/双EOF，
BEGIN/END完整，TAIL及时。END与inner不能替代caller退出事实。时间口径分别见projection：
固定测试、带5库oracle的inner、target/drain、完整caller均分开；这些不是容量验收。

全部DB/sidecar、nonce、完整source capsule和详细oracle仅留PRIVATE原件；PRIVATE-SEAL
记录长度/SHA，不制作或发布ZIP。公开仅显式raw allowlist、有限投影及digestinventory。
回滚停止此测试入口并保留原件，不删库/sidecar，不改旧authority，不热换金融代码。
不再运行SQL或新CODE。独立RAW、故障/进程恢复、DUE/scheduler、opsAuth/custody、
managed/HA、校准、容量与真实资金审批仍OPEN。
