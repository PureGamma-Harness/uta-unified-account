# Warm-cache fixture：连接关闭与强制GC证据

本提交只修复独立测试的资源管理，不改变缓存、账务、fence、行情或任何金融运行模块。
旧OWN `6961e5455f1443a3e6ce94c8788d5080c14fccce` 的两处 `with sqlite3.connect(...)`
只完成事务提交/回滚，没有显式close。SQLite连接的事务context不承担关闭连接的职责。
本组将其改为外层 `contextlib.closing(connection)`、内层仍保留原connection事务context，
成功和异常路径都关闭，全部金融/故障断言不变。

旧版实际Py3.13负控在warnings=error并每案后强制GC时，8项金融断言仍OK，但父进程捕获
4次ResourceWarning unraisable、子owner退出时还有1次未关闭连接警告；最终被测进程
returncode1、forced_gc_qualified=false。不能把原普通8项通过称为无资源告警资格。

同一测试仅修改上述import和两处context后，以单CPU顺序运行同8case；父每案后GC、
套件后再GC，warnings=error继承给真实spawn子进程，结果如下：

| runtime | 测试 | 耗时 | 被测进程退出 | ResourceWarning / unraisable |
|---|---:|---:|---:|---:|
| Python3.10.22 / SQLite3.53.1 | 8/8 | 2.508s | 0 | 0 / 0 |
| Python3.12.14 / SQLite3.53.1 | 8/8 | 2.248s | 0 | 0 / 0 |
| Python3.13.5 / SQLite3.46.1 | 8/8 | 2.103s | 0 | 0 / 0 |

旧负控只在3.13执行，没有声称所有Python版本均提供同样的析构警告机制。
新测试SHA256为 `01c340bfa582f1ae7014996aace740bf460b16d6b30445578250f90c8c797c29`。
原测试8case的实际warm hit、接管旧owner拒写、真实expiry不复活、原guard/audit腐坏、
未知COMMIT先RO查原风险row等断言均继续通过。所有故障schema保留在各自证据，没有修回
触发器掩盖故障。手动SQL-managed单authority harness仍不代表完整Router或容量验收。

[新证据manifest](evidence/warm-cache-guards-closing-20261117/manifest.json)和XZ保留旧负控、
三版新运行的全部before/fault/原错误与实际driver；读取每stage `run.json`中的被测
returncode与forced_gc_qualified，不以记录器自身退出码判断通过。driver源码及输入hash
均保留。JSONL每记录含原文件UTF-8字节及SHA256，无金融DB或客户数据。

旧6961的659条压缩raw原样保留，其SHA256仍为
`562d0511bf5f04608b44781e951bd1bdfaf65898a6c8c823658e27db47c2fe64`。
720基线也未修改；该fixture没有参与720的B/P/S运行，不能据此解释其S1内部异常。
没有新的负载、性能收益、缓存启用或生产批准；默认cache0不变。

部署仅更新测试代码并运行上述focused强制GC检查，无schema迁移或资金操作。回滚测试
会恢复已知未关闭连接，故不能把旧普通unittest OK当作资源资格通过；历史负控和原archive
始终保留。后续性能仍等待原异常取证、新冻结和集成负责人GO。
