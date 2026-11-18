# PR40 首CI与原生SQLite功能验收补充

此补充从已发布候选C `a2434bdfe711ead1d202f6c1527e527f73e2dfa2` 创建独立工作树，
合并首验作者历史及独立审查。UTA全树、原tests、MANIFEST、pyproject和CI配置与C
逐字节相同；没有新ordinary测试、新测试执行、SQL、构建、压测或CI重跑。
新增提交均为 `[skip ci]` 的已实测工具、只读reader、原件及说明；snapshot默认仍OFF。

## 首CI：精确head失败与PR-event成功分别保留

| 首attempt1 | run | 3.10 | 3.11 | 3.12 | 3.13 |
| --- | --- | --- | --- | --- | --- |
| C精确head push | 44241282705 | FAIL | success | success | success |
| PR-event /独立merge ref | 44241334703 | success | success | success | success |

PR merge tree与C相同，但资格不同。四绿来自provider原metadata，未下载成功PR unit
原件扩充逐条source/count结论。push失败原件记录2061 tests/1FAIL/0ERROR/0skip，
367份源摘要等Git C，十二项新selector ID各自ok。唯一失败是durable_faults:1461
的有界SH捕获前置，未证明到达后续五秒恢复断言，也未证明撮合优化是根因。

89541B connector unit ZIP及三members、27619B connector-decoded原log保持字节不变；
原private零字节direct-download文件不是此ZIP。独立只读closure1324309核三CRC、
Git源、计数及失败阶段，未重跑。一个成功push3.11的小package报告核19CRC/七check、
62runtime、6885required paths、22候选路径，installed八项和八命令通过。没有下载
wheel/sdist原payload，也不能用单job报告覆盖push失败。

[首CI分析](pr40-first-ci-independent.md)、[定向原件](pr40-first-ci-raw-export.md)与
[独立终态核验](pr40-ci-first-terminal-independent.md)单列范围，原五safe记录、
七raw导出、PENDING历史与manifest不回写。

## 纯组件与实际SQL证据分列

源26fa628的唯一首pure：12/12、Python3.12.14、CPU[0]、四源前后相同。
独立原件核验5fa9400保持原scope；它没有执行实际SQLite金融链路。

实际SQL唯一源为3b0c49a，四场景各以scan/snapshot建新私有库，共八库。
每模式分别六个真实匹配/十二fill；两组authority复用业务ID，不合成全局唯一吞吐。
同价FIFO/STP/部分成交、RO连带取消、真实第二侧seller账户冻结拒绝后的savepoint
回滚、无流动性与halt恢复均完成。八库重开财务投影相同，完整ledger哈希/分录、
数量/成本/费用/预占/业务ID与strict匹配及独立现金流回放通过。

非空六库各一条实际FILL历史数值回放通过，不能说全部决策都已重放。
独立reader7cd908a另以原JSON重算ledger链、逐币守恒、仓位成本、累计fee和五字段
估值；其首版错误地免除了RO adverse loss，首错误及源69b4958保留，修正一行后
reader通过。该失败属于审查器自己的规则假设；交易target没有重跑或修改。

独立结论为 **SCOPED_ACTUAL_SQLITE_EVIDENCE_PASS**，仅本单进程、合成legacy USD
四场景。63源原件/mini副本前后相同，实际加载18个UTA origin。完整11份报告、
原stdout/stderr、inventory及SHA保留；私有DB二进制不进Git。详情见
[首实际结果](matching-sqlite-first-result.md)与[独立验收](matching-sqlite-first-actual-independent-review.md)。

END driver10.144206064011087s是功能probe内部耗时；没有外层完整monotonic计时，
不是E2E吞吐。观察到的8,602,820B逻辑长度低于64MiB监测预算，不能证明未采样
C写峰值、kernel quota或阻塞I/O硬期限。Python3.12.14/SQLite3.53.1使用builtin
模块，extension path/SHA为null；loaded libraries为NOT_OBSERVED，不宣称完整attestation。

## 合并、包装与回退

以merge保留3da首验、7cd独立reader、cc415首CI和1324309独立CI closure的作者提交；
3b builtin修正、d517未执行计划与26fa首pure源码仍可达。独立review基线bb7没有
覆盖已修正driver。新隔离稀疏树的19份旧证据最初未物化，逐项从Git准确恢复，
只影响该新树；原工作树、原件及spent private roots不动，另有准备记录。

静态MANIFEST逐项选择新md/json/py/txt/log/zip；已有suffix和两条M0精确sha256
include均保留，没有扩大模式。本补充树的sdist/wheel/build/install未重新执行，
静态选择不等于新归档已实测。检查与逐文件Git/现场绑定在
`evidence/reviews/matching-post-delivery/`，manifest自引用明确排除。

没有数据迁移，没有服务入口或账户模式变化。部署仍使用默认scan，不能把这些
证据当作开启snapshot的运营审批。回退此补充只影响控制工具和文档；金融记录、
原件、schema/guard不删改，已有运行writer不热替换。实际启用、配置产品模型、
managed并发、复制/HA、真实USDT/USDC、现货借贷生产门槛、持续万笔、长稳及真实
资金批准均未因此关闭；首精确push仍FAIL，生产仍NO_GO。
