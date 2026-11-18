# Actual adapter once02：独立只读验收

固定封存 `eeaa9558df6a435f1bb2753d3d2c4390f850dfc2`，输入source `c076b0dc1feb765686de9c78683a4e4bea5429e2`。**SCOPED_ACTUAL_ADAPTER_EVIDENCE_PASS_WITH_EXPLICIT_LIMITS。** 独立审查未重跑adapter、pure6/12、目标模块或任何业务；没有读取旧job、密钥、数据库或查询过去PID。

## 独立复算与原件核对

- 八项输入在before/after map、source Git和封存tip逐字节匹配。原exit0、219,154,705ns、stdout214B/SHA `7b52ed91226aaf4b7959d3f6da63e3594ad419cc3e32da98fe1e55a865e2c053`、stderr0B均一致。
- 对唯一获准的新synthetic目录control/observer做有界、nofollow的完整只读清点，再对24个固定普通文件用NOFOLLOW/NOATIME读取、核前后stat稳定；每份原件与Git delivery copy的length/SHA完全相同。没有额外普通或特殊文件。
- 独立JSON/CAS解释器不导入生产codec或Coverage。它检查严格JSON、domain hash、canonical bytes、array count、anchor与heap/in-order关系，访问全部11个CAS节点，并重建四个完整report。每个report与独立literal schema/数值、对应receipt、timeline序号及latest一致；四份consumer receipt与此小合成例手算一致。
- 30330B总量由24文件实际长度相加得出：CAS11文件11515B、四receipt7096B，其余控制记录/timeline/latest均计入131072B同scope上限。另214B outer raw与30330B delivery copy明确单列。`28846 + result1020 + cleanup464 = 30330`可复算；这不是物理allocation、power-loss或长测容量证明。

四份完整报告canonical长度为1022/1023/1023/1023B；按已冻结wire协议独立重建帧长1184/1185/1185/1185B，第一帧与captured live记录一致。原probe没有另存observed kernel wire digest hex；独立记录只计算标为**expected**的wire hash。实际kernel hash相等这一运行期结论依赖冻结源码中的比较guard和原exit0，不能写成再次独立读取了历史pipe bytes。

## Phase与清理的证据强度

原first-frame-live记录BufferedReader、匹配PID/birth仍alive、未stdout EOF及1184B完整帧；冻结代码在该检查后才创建release。其时间早于queue观察，PID/birth与provisional result及cleanup一致。queue记录size2、cap2，最终batches `[1,2,1]`、next sequence5、无queued/pending/protocol failure、stdout EOF=true。

queue满时child_exit已经0，所以此记录证明raw queue占满及reader侧背压，**不证明kernel pipe堵住writer或生产者饱和压测**。stdout_fully_retained=false与读取到EOF分开，不把stream hash-only当完整raw保留。

cleanup记录constructor完成、确切binding、birth建立、原child exit0、创建两drain threads且无存活者、无fallback/信号。原launcher后续记录该birth不再出现。Popen wait/reap、drainer finally关闭、同node put/receipt query未增量、零quota后consumer恰一次等瞬态事实，只能按已封源码、原捕获和exit0作来源绑定；审查者没有重执行wait、put、quota或查询过去kernel状态。当前完整CAS图、唯一receipts及独立重建另外提供了可复算的结果证据。

## 次数与历史保留

metadata preflight attempt2与该source实际probe调用1明确区分。22e的FileNotFound发生在source closure、intent和target Popen之前；fce只恢复获准八项物化。它们分别4个新增文件在本tip逐字节保留，不能删除首错误或把metadata recovery算成新native预算。旧dc1实际首FAIL c9的9个新增文件也全部未变。

独立只读reader先固定在 `0585fe35806f35294d1530aecd5e6e72311f876a`，实际outer265,129,292ns/exit0，stderr空；完整结果与执行来源见 [独立复算](../evidence/reviews/observer-adapter-once02-independent/first.stdout.json) 和 [执行记录](../evidence/reviews/observer-adapter-once02-independent/first.execution.json)。reader只读Git及这30KiB新synthetic输出，没有导入或执行目标代码。

## 验收与回滚边界

本结果覆盖这一次小型合成pipe/report-FS adapter。实际watch/controller main、SQL、金融golden、撮合/结算、真实交易worker、HA、长时增长、内核故障和万笔容量均未验证；hash未提供签名、数据真实性或金融授权。生产及真实资金批准仍为false。

本OWN仅新增独立reader、原件绑定结果和文档，无服务、schema、参数或原数据变更。回滚移除本OWN新增材料，保留24份原件、历史首失败与全部预算记录；legacy仍默认，不自动启动或恢复长测。
