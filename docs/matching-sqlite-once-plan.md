# Snapshot selector：一次实际 SQLite 功能链路计划（未执行）

本计划依赖源26fa628的首次12项纯组件通过和独立原件审查5fa9400；二者均不证明
实际模块可导入、SQLite 结算或性能。本计划只交付新的 CODE/范围；尚无实际执行 GO。
旧纯源码、三份未执行历史计划和037首原件一字节不改。root 的公开 Draft 候选独立冻结，
本计划的两个新 runner 不混入其首次 CI 源码。

## 固定范围

只使用原生 `ExchangeService`、`Database`、`DurableLedger`、`DecisionAudit` 和
`Matcher`。每个场景分别建立 scan/snapshot 两个新私有文件库，共八个 authority。
`decision_audit=True`，默认真实 UTC clock、默认五秒市场 TTL、默认0.0004费率、
USD八位最小单位、legacy None policy；不改类或实例方法。每个风险操作前只发布一次
真实新鲜行情，失败不重采、不重发直至通过、不改变时钟。

| 场景 | 原生行为与人工断言 | 每模式确认成交 |
| --- | --- | --- |
| 同价FIFO / STP / partial | self-maker先于self-taker；撤较新自己买单，再按时间成交两个买单；4账户余额各9999.96；剩余-2保证金20.08 | 2 |
| 部分减仓连带取消RO | 真实对手开仓+3，再挂-1和-2 RO；普通-1先成交使后RO失效，随后第一RO成交；剩余+1/成本100/余额9996.8012，后RO零成交且取消 | 3 |
| 第二侧真实拒绝 | 买卖均已接纳；用原生 `_liquidation_state` 在新库写seller=LIQUIDATING作为明确测试故障，原SELL账户检查抛account_frozen；BUY已执行的第一侧必须随savepoint回滚，只撤seller | 0 |
| 无流动性 / halt / resume | 单边不成交且保留20.0792预占；实际交叉盘口暂停时保持财务状态，恢复后真实成交，双方余额各9999.9208 | 1 |

总计每模式六个确认匹配、十二个双侧 fill。不同 authority 对比刻意复用相同合成
业务ID，不能把两个模式的同ID总数叫全局唯一吞吐。没有按标记价制造 fill。
SELL冻结是本次小型故障注入，不冒称完整清算状态机或运营审批已验收。

每个库均：完整读取订单、真实回执、fill、仓位、本金利息投影、逐币分录及哈希链；
关闭本次所有事务后重新打开同一文件；重开前后财务投影逐项相等；
`ledger.verify`、`Matcher.verify(strict=True)`、已有独立现金流/成本回放
`reconcile_exchange` 均必须通过。非空成交库另抽取一条实际FILL决策做原数值重估，
不把这个抽样说成所有决策回放通过。

## 比较字段与原始证据

两模式的余额、逐笔分录（含完整哈希链）、仓位数量/成本、订单数量/已成交/状态/
费用累计/rowid/预占、成交量价/业务ID、风险权益/IM/MM/可用额及账户版本逐项exact。
不做浮点近似、价格/费用容差、四舍五入后比较或把财务差异改成零。

仅三类明确时间字段 `created_at`、`observed_at`、`recorded_at` 在比较投影中排除；
原始SQL行和原JSON全保留。行情快照ID由不同真实UTC内容产生，不跨库比较该ID；
每份行情完整payload的SHA/ID及MARKET_PUBLISHED引用/版本/时间先在各自库独立核对。
决策原快照引用也必须存在，实际数值抽样按各自原行情回放；决策的操作、前后状态、
版本、财务summary仍精确比较。不能以这个有限例外排除金融字段或业务ID。
无流动性和暂停分支只允许新增一次真实行情事件，其他事件/财务变化均失败。

八份完整原JSON（包括重开前后、最终SQL、关键中间状态）以O_EXCL写入私有reports，
每份上限4MiB，文件fsync；不宣称目录崩溃持久性。输出完整首stdout/stderr、实际exit、
源前后摘要、loaded UTA origins、运行时/SQLite扩展摘要及新目录文件库存，不提交DB文件。
没有原始成功结果时，不从部分checkpoint补造成功记录。

## 源码与执行预算

冻结清单严格为61个 `uta/*.py` 加 `sqlite_case_once.py`、`sqlite_once.py`，共63个输入。
独立准备记录将逐个核regular非symlink、len/SHA、Git mode/blob及现场物化；不得将
Git blob存在当作本地文件已存在。只复制这些文件及清单到新的只读mini source，
小于2MiB；不复制约209MiB仓库。运行实际UTA模块必须来自mini source，原源和副本
前后全部摘要相等。用 `python -I -B`，不生成或读取已有应用pycache。

一次进程，一颗允许CPU（记录实际编号），30秒driver期限；零应用线程启动、零worker/
子进程、零网络/TLS/AuthDB或其他历史authority访问。禁止所有 `/proc`、pidfd、信号和
PID操作；不读取或操作任何旧受保护进程。源包含未加载的模块不构成授权执行它们。
独立审查后 root 给出确切源/manifest SHA和全新 `/workspace/NAME` 才可执行。

stdout+stderr合计512KiB硬上限，先reserve再写FD，另保512B失败trailer；部分写失败
sticky own-exit125，原样保留首raw。预算到期own-exit124，不发信号或试图清理别的PID。
新私有run目录的source、DB/WAL/SHM和reports合计逻辑长度预算64MiB，已知Python写入
前reserve，步骤前后及应用行间约250ms检查SQLite文件。**这不是kernel目录quota**；
C内瞬时峰值和阻塞I/O不具有已证明的硬实时上界。超过预算/无法完整观察/未完成任一
mandatory检查即FAIL或UNKNOWN，不把未检验数据算通过。30秒不含任何重试或warmup。
所有失败数据保留，未获新独立范围不得再次运行这个case。

预期命令（占位符仅在冻结后由root替换）：

```sh
python -I -B evidence/reviews/matching-selection-snapshot/sqlite_once.py \
  --run-root /workspace/NEW_FROZEN_SQLITE_ONCE \
  --source-commit FROZEN_SOURCE_40HEX \
  --approved-manifest-sha256 REVIEWED_MANIFEST_64HEX
```

CLI标志或清单本身不授予执行权限。普通模块导入、元数据准备、真实SQL、故障以及性能
各有范围，不能在事后把首次试运行更名为预热。

## 验收与回滚边界

即使成功，也只称新的单进程SQLite小型功能链路通过、等待独立原件审查；无
managed fencing、跨进程竞争、复制/HA、真实托管、全决策重放、30分钟开放环、
万笔吞吐、首批真实产品或资金启用结论。snapshot仍默认OFF，worker/CLI未接线。

新目录不覆盖既有库，不切换任何真实writer。失败时保留新库/WAL/SHM和原始raw供
下一独立恢复任务，不删库、重新生成ID或自动重跑。代码回退仍恢复默认scan且保留
已确认财务记录；本实验没有数据迁移，不降级既有schema/guard。

## SQLite二进制描述的CODE修正（仍未执行）

独立组发现d517无条件读取_sqlite3.__file__不能支持builtin。3b0c49a只改结果
metadata：精确ModuleSpec/name/origin、BuiltinImporter和sys.builtin_module_names
三侧一致才记builtin，path/长度/SHA为null；动态扩展须ExtensionFileLoader、
modulefile/specorigin/loaderpath一致才哈希真实regular binary。未知组合失败关闭。
本次执行时记录sys.version、sqlite3.sqlite_version和已解析解释器实际SHA；
loaded_libraries=null/NOT_OBSERVED，不读proc/maps，不复制历史maps为空作当前事实，
不声称完整runtime attestation。旧d517清单/计划/首物化记录原样保留为NOT_RUN/0attempt。
61UTA、四个金融场景、fee/TTL/defaultclock、64MiB/30s/raw512KiB及旧PURE037均不变。
