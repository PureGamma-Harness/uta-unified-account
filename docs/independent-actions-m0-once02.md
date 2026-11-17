# Once02 PREP：修复首个实际run的源码checkout ref

原实际M为 `c71ed1756168072e0d8daea207a0d086a6dd1171`，sole parent控制C为 `5a72b6abd07c5030604b596cc74e19b18ffee23e`，唯一diff为新增 `config/independent-m0-approved.json`。root只向原literal分支推送过这一次。实际run [44169093697](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44169093697)、job134343020252、attempt1在2026-11-17T20:25:45左右源码checkout失败；runtime设置、pure控制测试、controller execute均SKIPPED，B/P/native未启动，public verify因目录不存在而失败、upload SKIPPED，provider artifacts=[]。这是首次实际工作流尝试失败，不是金融负载或SQLite/native测试失败，更不能计作完成M0。

已确认根因：sealedC once YAML的真实workload step写成短ref `909acecd153e2e89dfe2238e3ed3a3d3c9f0`，而正确source为40hex `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`。文件别处bootstrap的SOURCE断言正确并不能保护实际checkout字段，旧 `assertIn(SOURCE, workflow)` 检查过弱。这一拼写错误本应在发布前由精确步骤检查抓住。

原provider observation、M/C sole-parent/only-A关系、artifact缺失与安全脱敏checkout摘录已保留。完整原log继续私有，Git仅保其33,024字节和SHA256 `f4f9d85ac1c5c0fd6235083f3c0617e2430c7f872bd5f6264286bca8e51278b1`、选定行号/安全摘录；这是connector-decoded UTF8 log，不声称raw provider ZIP。未发布完整log、签名URL或private原件路径。

另一次**本地**错误提交 `2bccd65bc639be035dfe94c701eff1ced389b665` 是未初始化sparse index导致5656项删除、5657项diff，root的only-A检查已拒绝，never pushed，backup ref `refs/heads/evidence/m0-registration-first-index-error` 保留。随后真正远端M使用完整read-tree C的独立GIT_INDEX_FILE，仅新增marker。此本地index错误与远端checkout短ref是不同事件，原件分别保留，不改称同一故障。

本修复只将实际workload checkout字段规范为exact SOURCE，并给两份workflow都检验其唯一 `path: workload` step的pinned checkout action和literal ref：必须40hex且逐字等于SOURCE。新pure负控只改变该ref，原bootstrap SOURCE断言保持原样、`assertIn(SOURCE,text)`仍通过时，精确字段检查仍须拒绝。还拒绝duplicate/missing workload step和错误的另一40hex。新增检查已加入两份control sparse checkout，first-red在sealedC旧源码实际失败，原stdout/stderr/代码SHA保留；新的first-green不覆盖它。

原once分支、M、run与attempt永久不可变，不删除重建、不rerun追绿。下一候选使用新的精确literal `refs/heads/perf/approved-m0-20261117-02`、registration ID `independent-m0-20261117-02`；controller与workflow及defaultfalse模板同步pin，新pure测试明确拒绝原ID和原branch复用。format2、source909、业务argv、budget64/96/32MiB/fresh2,348,810,240字节、crypto协议及recipient pins保持不变。加密模块和source运行时不改。

当前只CODE/PURE/local PROPOSED JSON准备，没有第二个M、触发分支、push或dispatch。default模板仍false/C全0。新C、controller/两workflow哈希及fresh900秒workspace参考必须由root重新审；root最终才可决定sole-marker-child M和一次精确push。旧proposal/原run/first失败都不覆盖。是否有实际M0须以新provider原始状态与持久回执为准，不能由pure测试或JSON旗标宣称。

PR22 stopped-owner恢复缺陷与monitor locking-protocol栈仍按known-issues保留，source909历史8CI PASS不覆盖它。所有生产/容量/HA/可靠性放行false；若批准once02，也只能合成低量本地SDK诊断。没有SQL、native金融负载或crypto批次重跑，也不动旧新长任务/原存储。
