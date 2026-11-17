# NORMAL cache：763202d 隔离集成候选

状态：**默认关闭、NOT ENABLED、无性能验收**。本轮未运行benchmark、全量大历史压测或
改变任何生产/24小时任务。只有小型正确性和只读审查结果；后续须新freeze完整CI/包与GO。

## 来源与精确提交

隔离工作树 `/workspace/uta-normal-cache-current`，基线
`763202df9cb3ce089721e5281371aff3eab58089`。其runtime逐字节同7ae94eb；额外fixture修正
与旧红/CI归档保留。此前根release历史树2328690和实际integration分支分开，本组没有
修改root、任何frozen树或原producer887/observer源码、DB、PID、开始/截止时间。

运行正确性冻结候选为 `fdbd95b72a654ccf37d1e492db40af281c8cb28b`，包含下列完整栈。
不能只移植测试而漏运行实现，也不能把旧190直接覆盖当前owned-startup路径：

| 原提交 | 本次映射 | 内容 |
|---|---|---|
| 190aa9ba8e99da2306a6dec3d1cc62e2cb93b9d8 | 9af4c2aecf0fb300c3906b65464c6b4778cc539d | runtime移植并适配当前native prepared worker，补当前metadata key与7项集成测试。 |
| cb85d6896ada7319c81bebd3a67db72da2cd10d8 | 8395ee538bfe9765ea52206f1832d9901241cfe5 | 真实managed owner开仓、部分清算、冷重启测试。 |
| 639a2db24991b2b6b8ca61215a3939b1d0c4a9be | 03f49da44f299714ea4a1c1c34dfe928b3798005 | 独立14用例及真实原5c53十步财务golden。 |
| 6961e5455f1443a3e6ce94c8788d5080c14fccce | c205297415949cd881d509001dfd32c4effec4e0 | 独立warm-cache guard/COMMIT八用例与原红绿证据。 |
| 0acb69bdae73571521460fce2f4a83dace06336c | fdbd95b72a654ccf37d1e492db40af281c8cb28b | SQLite测试fixture显式closing与旧强制GC负控，不改金融运行模块。 |

## 当前启动边界

旧190仅传容量给新建ExchangeWorker；当前root在完整ledger回放前原生预建worker，
之后要求复用同一对象。直接旧patch会丢容量或错误地在freeze后重建Matcher/调度DDL。
本集成将容量从父settings送入 `_OwnedStartup`，在prepare_schema的原生构造前校验和设置。
take_worker校验容量、原生类型、exchange绑定、无线程/未运行/无proof后交接该原对象。
`_schedule_schema()`和原source-defined准备顺序保留，没有冻结后创建第二个worker。

实际 `_run_worker` 的actor writegate、完整ledger/credit RO回放、full managed spot核验、
final fresh fenced COMMIT和READY顺序均保留。启动验证不是NORMAL证明，也不从LRU取验证
结果。新owner/cold restart重新空缓存，没有预热；命中只省重复NORMAL监督，不产生资金、
订单接纳、匹配成交、清算完成或readiness凭证。

default0继续原事务/监督路径，不构造依赖hash。非NORMAL仍实际监督。可选路径仍以bound
database.read_transaction取得同一t0，先执行原 `_market` 的policy/schema3/audit校验，
消费命中前再以真实时钟检查该原snapshot年龄；不改observed_at或TTL。每次金融变更和
matching仍由当前事务authorizer、持久SQL guard、原生writer和COMMIT检查授权。
`supervise_account(connection=...)`只加入原活动同authority连接；`_using`负责登记/数据库
身份，SQL角色及fence由原TransactionGuard约束，没有把RO证明当写入权限。

## 当前依赖与完整性范围

保留完整账户/gross债务、仓位、所有live线性与spot锁、risk state/cycle/revision/plan、
完整market、配置/实际运行政策和分片全局ledger head；补入原ledger_schema行、
spot_schema/config行与相关table/index/trigger SQL定义。未版本化的这些变化也不能复用旧
NORMAL；新增测试在原version不变时实际观察fallback，并停止在完整监督入口。
这些raw schema/policy改动是隔离故障探针，不是允许在线更换模型或批准损坏schema运行。

这不是全journal/spot history的验证缓存。原精确官方ledger guards、credit/spot完整性
检查仍在native启动阶段执行；managed live spot义务仍报managed_spot_state_unsupported。
没有增加产品/模式或改变金融成功集合。代码/配置生命周期不可变及SHA256抗碰撞前提保留；
不宣称防御拥有宿主Python私有对象修改权的攻击者。

更全metadata增加成本：无spot每miss额外至少26次SELECT，有spot至少32次，尚不含实际
监督/guard；完整live-order扫描、JSON/hash与全局ledger/head、行情更新失效都可能负收益。
t0后变化仍按原固定N公平轮次后续检测，ceil(N/B)+1不是毫秒承诺。未用关闭后台、缩短TTL、
放宽freshness、切换成功分类或减少依赖来换收益。

## 实际小型验收

所有运行顺序单CPU，warnings=error，末尾GC；无ResourceWarning，源码前后hash一致。

| 目标 | runtime | 项数 | 实际耗时 |
|---|---|---:|---:|
| 9原cache + 14独立 + 8 warm + 7当前startup集成 | Python3.10.22 / SQLite3.53.1 | 38/38 | 17.426s |
| 同上 | Python3.12.14 / SQLite3.53.1 | 38/38 | 16.504s |
| 同上 | Python3.13.5 / SQLite3.46.1 | 38/38 | 17.236s |
| root原OwnedStartup/Reference/OwnedSpot保持 | Python3.12.14 / SQLite3.53.1 | 30/30 | 7.359s |

新7用例覆盖：0/8原生prepared对象和真实ledger/credit调用、freeze后0DDL；容量/对象不匹配
拒绝；缺官方ledger guard时原生ledger构造保护检查已拒绝，不能抵达完整replay/READY；
metadata变化实际失效；真实两个owner PID
分别冷capacity8/size0、bound query_only spot验证实际执行；live spot封存仍拒绝。
14项仍逐表匹配原5c53财务golden，不只比较候选两臂调用数。

首个集成测试红是fixture把owner generation写死1/2：离线seal先消耗一代，实际为2/3。
修复为读取启动前持久generation，再要求两个实际owner连续+1/+2；同时等待第二个真实
READY后关闭，避免把测试清理stop误作初始化失败。没有改运行lease、READY或金融逻辑；
初红和后续日志均保留。旧6961 ResourceWarning负控及原归档也原样保留。

[原始记录与hash](evidence/normal-cache-current-763202d/manifest.json)绑定fdb候选与完整代码
fingerprint；本报告后的归档commit只新增docs，不改已测运行代码。独立只读peer审查763到
fdb未发现阻断项，明确native startup/权限/当前依赖前提；它不是fullCI或性能签字。

## 部署与回滚门

这是隔离集成候选。默认normal_cache_size=0；仅在完成新源码全量/安装/CI、独立风险时延
验收和明确GO后考虑显式选择非零。0/opt性能对照须同源码、同输入，保留实际失败和负收益，
不得拿旧7a或不同政策/epoch路径计算gain。本轮没有运行任何此类对照。

回滚只需停止入口、查询原CID并排空/对账、关闭旧owner后以新进程size0重开；无需schema
迁移、改账、释放在途OPEN预占或恢复LRU。产品/权限/保证金模式和实盘资金上线审批边界不变。
