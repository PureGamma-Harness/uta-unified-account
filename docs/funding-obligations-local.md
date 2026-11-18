# 本地持久资金费义务：CODE 规格

基线为公开PR48的 `6ba5ba2e9334f30be949f368d036c96fe9857c30`。新隔离分支只准备
本地单authority/USD/Cross/乘数1线性永续纵向切片；不接REST、默认worker、真实资金或
后台timer。当前目标compile/import/SQL/test/worker/bench/CI均0。此前owner、32个封存
原件、历史policy/receipt、first-CI来源不修改。参考政策仍是原有限公开资料摘述及明确的
本系统规则；没有新的外部交易所精度或边界行为证据。

**能力边界仍OPEN：pending资金费尚未进入订单/提现/划转预占，本接口不保护这些外围路径；
旧binary排除不是managed fence；最终claim检查不承诺物理COMMIT/fsync早于leaseUntil。**

## 权威、状态与查询

新fresh-only capability与旧 `FundingLocal` 互斥，不在旧authority热装。新schema有不可变
config、schedule身份、cut、command result、applied receipt和append-only转移日志；
task行保存当前状态/claim generation/owner/随机nonce/到期及最后原因。产品+canonical UTC
period全局唯一，稳定obligation业务ID唯一；任意command ID跨所有动作唯一。相同command
与完全相同参数返回原提交结果，内容变化409，不重新运行、不延长claim。

| 状态 | 经济含义及允许动作 |
| --- | --- |
| SCHEDULED | 义务已登记，未到标签；可查询/到时转DUE/短claim，不能提前现金结算 |
| DUE | 已到时而未支付；可claim、准时cut、应用或转等待/人工 |
| WAITING_DATA | 边界或当前风险数据不足，义务仍outstanding；有可信cut可在数据恢复后新attempt |
| WAITING_CAPITAL | 差额缺足额真实treasury证明或现金；cut及应付款保留，允许新attempt |
| APPLIED | 现金、当前风险动作、分录、receipt及状态同事务确认；不可改写或重收 |
| REVIEW_REQUIRED | 缺历史cut/不可安全自动处理/核对错误；仍outstanding，自动执行停止，无豁免或清零接口 |

`query(obligation_id)`返回当前任务及cut/receipt引用，`command(command_id)`返回原命令
提交时结果；两者不是同一个时点。NOT_FOUND仅指当前读快照没有已提交结果，不能证明在途
动作永不提交。结果未知须先查询原ID、经串行claim/fence确认后才可继续；不能换业务ID重收。
资金不足等业务失败通过SAVEPOINT回滚全部现金/风险修改，随后在外层同一authority事务
提交WAITING/REVIEW原因和命令结果。存储不可用导致整个事务失败时，先前已提交的DUE/cut
保留，调用者结果UNKNOWN；不能声称写不进去的错误已经持久化。

`pending(after_id, limit<=100)`允许重启后发现所有未履行义务，包括REVIEW；不需猜测旧ID。
构造器只核capability/schema/code以允许已记录金融拒绝后的状态查询，不宣称账务健康；
`verify`显式完整核对，`apply`在writer事务内必须先完整核对。坏账务库可查询REVIEW但不能
因此通过金融验收。claim命令原结果含私有nonce，只供可信内部executor恢复，禁止公开。
schedule允许rate未知，任务以NULL保留，绝不当作0；准时capture可接收经内部批准的resolved
rate并绑定该命令和cut。缺rate/mark仍WAITING_DATA，超窗且无cut转REVIEW。原schedule
rate身份不改写；query另返回不可变cut中的实际已批准费率及应付分解。

## 准时cut及延期应用

cut只能在原政策0..2秒窗口内，由本authority `BEGIN IMMEDIATE` 的financial writer事务
直接读取合资格完整净0持仓、账户版本、事件序列、可信fresh market及mark、规则/config/
实际loaded code refs，保存完整payload/hash。不能由调用者提交账户现金或历史持仓；已存
cut不可替换。缺数据时持久WAITING_DATA；没有cut而迟到则REVIEW_REQUIRED，保留未知但
未履行的经济义务，绝不用现在仓位补造过去。wallclock标签不是历史证据。

有可信cut后，即使发生真实平仓，原资金费仍按cut的数量/mark/rate/最小单位承担。应用时
在当前authoritative账户、现金、仓位和fresh当前行情上重算风险，逐客户双分录、实际
treasury资本、reserve/clearing、版本、原supervisor实际撤单/只减仓计划、receipt及状态
同一writer事务确认。当前行情失鲜或supervisor不持久化时全部金融修改回滚并等待数据。
禁止把负cash变本金，不凭mark造清算成交，不假装过去仓位仍存在。新receipt分别保存
cut与应用risk market/当前账户前后状态，便于解释两个逻辑时点。

舍入继续逐账户向零、亚单位差按原规则当期豁免，整分差由隔离reserve承担；不足只能从
固定treasury既有确认入金/真实可用现金转入，资本证明仅在实际转移提交时唯一消耗。
等待中的attempt不消耗证明，不预先释放或伪造reserve；其他period竞争同一现金由writer
事务串行。无reserve提现/欠款豁免/运维解锁接口。全局逐币双分录与receipt逐笔核对。

## 单节点claim、重启及兼容

claim是这个本地义务执行器的代际fence，不是整所managed writer或HA租约。每次有效claim
在同writer事务递增generation，生成私有随机nonce，固定owner及100..5000ms短租约。
所有cut/apply需匹配持久token，并在金融提交前再检查未过期；新owner使旧token失效。
claim状态与经济状态分开，等待不会被claim动作清空。过期旧owner只可获得FENCED结果，
不写金融状态；已确认command重放优先返回原结果而非重新claim。

时钟采用受信单机UTC和持久非递减观察高水位；回拨拒绝，不能复活已观察过期的token。
此为明确的有限假设，不提供跨主机时钟/复制/HA共识。重开同库保留task/cut/claim/commands；
过期后新generation接管，原receipt和cap证明不变。同步 `execute_once` 只是一轮显式调用，
无后台循环或自动重试；失败需查询原ID和新授权attempt。未来两executor竞争测试需独立
授权恰好两个有界测试线程，CODE阶段不运行任何线程。
所有trading/资金writer仍须部署同一冻结版本；旧binary隔离由部署边界保证，本地claim
不具备排除任意旧binary或raw SQLite写入者的managed fence能力。DUE金额也尚未接入
统一订单前/提现/划转预占，等待期间的额外风险限制是生产资金启用前的独立OPEN门槛。

旧prototype安装/打开看到新marker明确拒绝；新安装看到旧funding_local、其他已用金融
数据或managed marker也拒绝。新增模块的实际函数/默认值/闭包/常量必须进入独立固定
artifact覆盖，不改credit `_MODULES`、unknown constant拒绝或live-state排除。当前源码
变化使旧artifact不匹配时走原拒绝，不静默重绑旧authority。

新artifact复用现有credit固定平台module closure并加三个funding模块，覆盖实际loaded
函数/默认值/闭包/常量，包括schema和transaction fencing helpers；不以source_files替代
loaded覆盖。仍保留1MiB capability/cut/receipt归档限制；超额拒绝，不临时扩大旧规则。

## 人工例子、验收及回滚

八组手算和固定六测试见 `manual-oracles-and-test-plan.json`。正常a/b各1000，开仓费用
.04，cut100/rate.0001后a999.95/b999.97。资本三账户差一分等待真实treasury入金后转入。
最关键的延期例子：cut q+1/-1、mark100、rate.01，之后真实平仓1@101，第二次费用各.05，
平仓后a1000.91/b998.91；旧资金费-1/+1仍须应用，最终两人均999.91，仓位为空、费用.18。
无cut的迟到、两executor/过期fence、原ID查询、rollback、旧cap互斥及未知金融常量分别验。
跨9个合成scenario DB计划9次撮合/18侧成交；业务ID可跨独立scenario重复，不能当全局
唯一交易或吞吐。未来exact runner/资源/SQL scope与独立CODE审核及root GO另行冻结。
固定未来测试全部使用显式合成reference clock，不是native wallclock lease精度验收。

## 901独立审查后的报价缺口修订（仍CODE）

账户审查 `ed1724a43b667d039d36d87483589bfc4b0fd162` 对901提出
FUND-OBL-001/002，原901及其NOT_RUN计划保留精确副本。新修订先校验必要产品/规则，
只将确实缺少必要mark或原生current-risk计算明确报告、且与snapshot缺key相符的缺价
归为`funding_required_quote_unavailable`/WAITING_DATA。没有把所有ValueError或
`risk_unavailable`改为可恢复；其他库存、配置、规则及账务错误仍走原REVIEW/拒绝。

`apply`在既有SAVEPOINT内、金融修改前增加一次每参与账户的原生current-risk检查。
这是额外重估成本，不提供准入授权或加速主张；原supervisor、最后fresh market与claim
观察检查全部保留。它按当前库存/订单实际需要报价，不盲目要求历史cut的产品mark。
最后观察之后仍有receipt/task/command/event与COMMIT/fsync，未提供硬提交期限保证。

真实publisher不能移除live仓位/订单的BTC mark。固定六方法/九库的missing场景先在
USD账户已入金、尚无BTC仓位时合法发布fresh USD-only，准时capture缺mark应WAITING_DATA
且无cash/cut。恢复完整行情后执行原1次撮合/2侧成交，再保留独立missing-rate及
late-without-cut REVIEW断言，未改为猜测历史持仓。current-data场景先断言真实publisher
拒绝live BTC下的partial发布，只在只读快照中给精确helper一个typed partial作为负控，
不注入/替换持久行情、不改history/hash/guards；该异常存储路径的持久恢复集成仍OPEN。
恢复完整fresh行情后继续已有stale→APPLIED流程。changed-positions场景真实平仓后合法
发布USD-only当前行情并应用历史cut，防止错误地把历史BTC当作当前仍需报价的风险。

上述子步骤仍计划9个scenario matches/18侧成交、46journal、fee.72/custody-15001、
8义务/5APPLIED/3outstanding，没有新的DB、撮合或金融分录预算。所有目标执行仍0；
新delta还须账户复审、独立风险cross及独立入口/root GO，不能由本修订自行签闭合。

部署只允许新合成本地authority。回滚停止显式调用并保留task、cut、claims、全部命令结果、
receipt、journal及事件；未支付义务和REVIEW不能删除。源码/规则变更必须停写、复核并通过
另行设计的离线迁移；本切片不提供旧库升级或历史catchup。禁止删除新表后让旧prototype
接管。真实运维审批/托管、DUE生产timer、commit/crash故障、长时间并发、时钟校准、
账户分片/复制/HA、容量和真实资金上线仍OPEN。独立账户与风险审查拥有否决权。
