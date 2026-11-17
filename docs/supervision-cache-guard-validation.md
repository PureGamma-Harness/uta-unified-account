# Warm NORMAL cache：独立 SQL guard 与提交证明故障验收

结论：本报告下述8项合成、单host正确性测试通过；没有性能或生产启用批准。
默认 `normal_cache_size=0` 保留；[同源码对照设计](supervision-cache-performance-plan.md)
仍为 **PLANNED / NOT RUN**，等待最终冻结SHA、完整验收及集成负责人GO。

## 版本、真实执行者与边界

根基于 `e033c43142d4ca70dc1076de68683a40990fa385`。运行依赖是实现组
`190aa9ba8e99da2306a6dec3d1cc62e2cb93b9d8` 和真实managed烟测
`cb85d6896ada7319c81bebd3a67db72da2cd10d8`；独立树复制为 `2af9283`、`c745dad`。
这两项不是本组OWN提交。本组只新增测试、审查/计划与证据文档，不修改运行模块。
另只读审查独立组639a2db的14项及原5c53财务golden，不重复使用其断言作为本组计算器。

每案启动一个真实spawn PID，获取自身30秒SQL writer lease，构造required audit开启的
Configured Cross服务和cache4的真实ExchangeWorker。实际运行一次建立NORMAL证明，
再运行一次并断言 `hits>0`、`skipped=1`，才进入故障阶段。parent和owner PID不同，
SQL owner_pid等于子PID。命令pipe只控制确定性故障顺序，不替代金融准入或计算风险。
所有财务写入与缓存逻辑使用原运行实现。

这是**SQL-managed单authority的独立owner故障harness**，没有启动完整
DurableProcessRouter协调器，也没有证明其自动选主/消息交接、网络、复制或容量。
缓存数据是进程局部证据，状态与账本始终留在同一真实SQLite WAL/FULL金融DB。
不把单独构造的worker用于解释887旧source长稳或新的managed平台全范围验收。

## 8项专项断言

| 测试后缀 | 实际证据和不可放宽的断言 |
|---|---|
| `warm_old_owner_cannot_write_after_release_and_new_pid_takeover` | warm后真实新单保留OPEN，手算预占`.001×100×.1 + .00004 = .01004 USD`，required decision关联存在。旧PID合法release、parent新PID取得下一generation后，旧worker round/deposit/submit/renew全被`writer_fenced`拒绝；同PID裸SQLite更新明确报缺少`uta_writer_fence_v1`，财务表全部不变。合法新owner入1 USD后余额精确1001 USD，订单仍只有原1笔。 |
| `warm_proof_cannot_renew_an_actually_expired_lease_or_commit` | 合法缩短TTL至`.05s`，等待真实单调时钟过期，无伪造clock；旧PID renew/round/deposit/submit均报`lease_expired`。generation/到期时间不被复活，全部金融和control表前后相同。 |
| `warm_hit_does_not_mask_missing_persistent_financial_guard` | 真实warm后在隔离库故意DROP财务持久guard，round/新单/入账均`fence_guard_corrupt`，hit不继续增长。后台线程报告worker_failure且无法声称已提交紧急halt；原schema损坏与财务事实保留，不自动修复。 |
| `warm_hit_does_not_mask_weakened_same_name_financial_guard` | 同名guard改成无效果`SELECT 1`，与缺失情形同样拒绝；验后仍保留弱化SQL，不能只凭名称或恢复后结果过关。 |
| `warm_hit_does_not_mask_fence_control_guard_corruption` | 故意DROP lease控制guard，真实warm仍须`fence_control_corrupt`，无资金/订单效果或静默重建。 |
| `warm_hit_still_validates_required_audit_guards` | 故意DROP `audit_order_requires_decision`，warm round和新单均`audit_schema_corrupt`，原审计校验仍执行，不能靠旧NORMAL绕过。 |
| `full_risk_row_and_model_table_definition_invalidate_without_account_version` | 分别变更NORMAL风险row的revision、核心仓位表定义，account version不变；每次必须完整supervise、skipped0，稳定后下一轮才能真实hit。DDL是隔离故障探针，不是已批准数据迁移接口。 |
| `warm_miss_with_failed_or_unknown_commit_cannot_publish_new_proof` | 先在原authority移除风险row制造确定miss，真实deferred-FK COMMIT失败时riskrow不落库；真实COMMIT后响应丢失时查询原alice风险row确认NORMAL已持久。两种情况下cache size均为0；先RO查原状态，再只重做同账户幂等监督，不重发资金或订单。后续重新证明再允许hit，ledger、账户、订单、fill、业务event全不重复改变。 |

过期/撤销lease的缓存hit计数可能在只读t0比较后、游标金融事务被拒绝前增加；
测试要求整个round失败且无法提交资金/订单。计数或旧NORMAL报告不是writer权限或ready。
持久guard和审计损坏则在本轮快照入口被明确识别，新增hit数保持不变。

## 对完整依赖和提交失败的复核

`_dependencies`包含完整liquidation row；`_common_dependencies`包含当前核心表定义、
`uta_schema`行、市场、配置、资产/ledger head和实际运行政策。因此风险revision或核心表SQL
不能在account version不变时继续命中。政策中有产品/抵押规则、精度、费用和行情年龄。
`ledger_schema`的singleton值、全部历史journal/audit内容没有被等同为该digest的完整数据库
证明；它们不是当前NORMAL监督每次读取的数值输入。正常账本/审计验收仍独立执行。
新增模型、表或监督输入需要重新追溯依赖，不能仅凭本次测试宣称所有未来schema已覆盖。

事务fault只在Database测试子类注入：原监督事务退出前插入真实deferred FK违例，或让
真实COMMIT完成后丢失返回。没有重写缓存、风控、SQL fence或金融方法。故障后cache必须
为空，说明证明未在COMMIT成功返回之前发布。删除riskrow为故障探针；unknown后的唯一
原标识是该authority内的alice风险row，查询它与全金融表后才推进，不换新业务ID补做资金。

## 运行与证据

三个runtime顺序执行，每次parent和spawn child仅继承一个CPU（实际affinity `[0]`），
无并行压测或profile。解释器为3.10.22/SQLite3.53.1、3.12.14/SQLite3.53.1、
3.13.5/SQLite3.46.1。

| 最终相同测试源码 | 项数 | 实际耗时 |
|---|---:|---:|
| Python3.10.22 / SQLite3.53.1 | 8/8 | 2.032s |
| Python3.12.14 / SQLite3.53.1 | 8/8 | 2.477s |
| Python3.13.5 / SQLite3.46.1 | 8/8 | 2.296s |

命令主体是：

```sh
python -m unittest discover -s tests -p test_supervision_cache_guard_validation.py -v
```

设置 `UTA_CACHE_GUARD_EVIDENCE` 为新的空目录，可保留每案故障前完整表/schema、owner与
源码hash、每个pipe请求及原始错误、故障后不修回的schema和金融事实；无环境变量时使用
测试临时目录。实际单CPU配置、解释器、全部测试输出及初次fixture失败均在归档中保留。
归档不含金融DB文件、客户数据或密钥。JSONL记录保存原文件UTF-8字节及逐文件SHA256，
可独立重算；[manifest](evidence/warm-cache-guards-20261117/manifest.json)描述完整清单。
最终测试SHA256为 `5ef406050f8606002b987d58136b0f0a755a001d83fd07a4c61461381d50a77e`；
659份原始文件记录压缩后267920字节，包含初跑、补错误字段前后和最终peer复核后的
各次状态/日志，不含SQLite金融DB文件。最终资格对应 `peerfinal-py310/312/313` 三个stage。

初跑8项为6通过/2失败，原因是测试fixture的ProductSpec没有显式ACTIVE，默认DISABLED，
合法单先得到product_rejected。只将fixture改为ACTIVE，没有放宽lease/guard断言；初跑
日志和每案状态保留。随后还为裸SQL拒绝增加明确UDF错误及SQLite errorcode记录，避免将
任意技术错误误称为持久guard拒绝；最终三runtime使用相同测试源码。
另经只读peer审查，在合法新单使旧key失效后，再明确断言新的 `skipped=1` 和hit增长，
才执行takeover；防止仅初始warm而没有带live订单证明时测试仍假绿。

本组不修改任何实际24小时producer/observer源码、DB、PID或历史开始/截止时间。
启用回滚仍是停止入口、按原ID查询/排空、正常关闭后新owner cache0重开，不改账或恢复LRU。
