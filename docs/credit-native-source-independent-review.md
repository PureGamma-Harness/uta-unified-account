# Native preparation source preflight：独立实际 RED/GREEN

审阅固定在集成`a4d4facc3235a324afbc0fdb19635bf0bbc86a75`，独立分支
`test/credit-native-preflight-reference`。静态最小计划先发送并得到GO，随后仅执行一次CPU3
顺序窗口：**0.890334秒**，含两份源码导出、两个实际子进程及清理，低于5秒总预算；每个
子进程timeout上限30秒，并受剩余5秒全局预算约束。未重跑29矩阵，没有服务监听、load、
live authority或原cash-deficit分支操作。

**本次source-preflight范围未发现未关闭阻断。** 旧source确实将两种坏来源提交到未来
`NATIVE_PREPARED`，安全断言保留RED退出1；新source在任何native DDL/marker之前typed
拒绝，健康准备控制成功但不授予owner或交易权限。它是未来准备态的金融来源准入缺口，
不是普通客户或当前public borrow成功的漏洞，也不证明新增贷款/audit/source/replay已放行。

实际source与运行时：

| 角色 | immutable commit | `uta/credit_native.py` SHA256 |
| --- | --- | --- |
| 原RED | `9e8d4ea0406db80ee93c94eb0bbfecd7b5058bfc` | `2f163047ac87c84d4aa36b2ab9446434984ad6145b887bfac5464bef6a469571` |
| 修订本体 | `26f7c59ec66f4553fcd135816509f02a00550de7` | `903ab01e0a7a5b4956b0bfb6ef00eac5cb4a946f376876eec70597f2d827950f` |
| 实际GREEN集成 | `a4d4facc3235a324afbc0fdb19635bf0bbc86a75` | 同修订本体 |

两份完整`uta/`均从各自commit的实际`git archive`导出到自有临时目录，分开子进程导入，
没有把旧函数猴补到新runtime。GREEN完整package来自a4；a4相比26f还含credit_artifact，
不声称整个package相同，已逐源保存全SHA256。实际bootstrap audit artifact给出两进程
Python3.12.14 / SQLite3.53.1。全部临时package及五个临时DB均已清理。

初始每个本地库通过原服务/信用命令建立：两账户各USD100、真实synthetic pool BTC1、
明确asset/account limits、QueueStore和真实schema3 audit；没有新credit cap或owner。
坏source只在enable前由受信测试SQL显式注入，没有公开客户调用或伪造verified字段。两个
源码使用相同金额与独立手写wire descriptor；policy/certificate内容hash由参考脚本自算，
没有调用生产serializer产生预期值。remote shard的claim只是完整证书声明，不冒称查过
另一片或外部托管。

| case ID | source / 独立坏输入 | 实际结果 |
| --- | --- | --- |
| `old:pool_projection` | pool journal仍BTC1；仅projection改为.5，descriptor opening pool也声明.5，原pool_funded claim仍为1 | 实际COMMIT，重开存在marker及43个选中的native对象；安全断言false |
| `old:masked_principal` | alice principal+.1、bob principal−.1，aggregate0；原journal/债务科目保持0，descriptor opening p/i均0 | 实际COMMIT，重开存在marker及43个选中的native对象；安全断言false |
| `new:pool_projection` | 同第一坏输入 | `CreditNativeError.code=credit_financial_source_invalid`，cause为原LedgerError：materialized balances differ from journal replay；实际ROLLBACK，schema及全部表原样，0 native DDL/marker |
| `new:masked_principal` | 同第二坏输入 | 同固定typed source错误；cause为原ServiceError：gross debt projection differs from its journal accounts；实际ROLLBACK，schema及全部表原样，0 native DDL/marker |
| `new:healthy` | 原健康来源，全部opening为0，pool1/claim1匹配 | 实际COMMIT到NATIVE_PREPARED；原金融字段不变，generation0、ownerNone、inactive、trading_enabled=false |

旧子进程在收集两项真实COMMIT和重开数据、完成各自cleanup后，执行“坏来源必须拒绝”
的实际assert，明确退出1及保留traceback；不是把接受坏来源当作绿色测试。新子进程执行
三项真实assert退出0；没有以SQL错误、超时或UNKNOWN洗成成功拒绝。

完整原始记录包含健康seed、坏seed的每条注入SQL及参数、全descriptor、prepare前后完整
schema/表、原方法调用、实际事务trace、重开fence事实、source/runtime及清理状态：

- [window.json](../evidence/runs/credit-native-source-independent/window.json)：实际命令、cwd、timeout、退出码、stdout/stderr和0.890334秒窗口。
- [old.json](../evidence/runs/credit-native-source-independent/old.json)：两项原始RED及重开marker事实。
- [new.json](../evidence/runs/credit-native-source-independent/new.json)：两项typed GREEN及健康准备控制。

静态及观察核对：

1. `_verify_financial_source`在真实`database._fence_transaction()`内，原fresh history、空
   inbox和audit schema核验之后，`validate_opening`及第一个`_create_credit_object`之前。
   新完整核验不会让“全片本金加总0”掩盖逐账户错误，也不会让pool projection自行声明
   的数值替代原journal重放。
2. 原`DurableLedger.verify(...,connection=...)`完整检查journal/hash、逐币投影、账本保护
   等；随后原`CreditService._verify`检查逐账户p/i对债务科目、limits、信用命令及pool。
   pool坏例先在ledger停止，因此没有误称其又运行credit；mask及健康两案均实际运行两者。
   健康原方法返回ledger3个events、credit0个非零债务。
3. 用`sys.setprofile`观察**原函数code对象**，没有替换任何原方法、返回值或验证器。两项
   新原核验的connection对象与helper完全相同，只有1个prepare连接，`in_transaction=true`、
   registry role确为control、guard绑定同一DB/connection；SQL trace确有BEGIN IMMEDIATE。
   它是原control W快照，不是新连接、只读快照、虚构startup token或“verified”布尔值。
4. prepare观测期间未调用ExchangeService/CreditService/DurableLedger构造器，未调用
   ledger.post、borrow、repay或deposit。固定view只提供原读取/单位换算方法，未返回、缓存
   或发给调用者；其中`Ledger(scales)`是纯内存codec构造，观测单列为PURE，不是服务或
   schema构造器。实际完整verifier源码也没有金融mutator调用。bootstrap构造器在准备
   观察窗外，是建立合法初始库，不混作source preflight。
5. 完整verifier通过后，原`validate_opening`仍在同连接核本地opening本金/利息/pool和
   pool_funded逐source/CID/数量；全证书、authority、scale及静态sum由实际policy模块验证。
   本次没有新跑fresh历史或错claim矩阵，不把此前29结果迁移为本次新证据；静态未见本
   修订改变这些前置门槛。

可复跑的独立实际probe为
[probe_credit_native_source_preflight.py](../scripts/probe_credit_native_source_preflight.py)：

```bash
taskset -c 3 python scripts/probe_credit_native_source_preflight.py --output evidence/runs/credit-native-source-independent
```

本次没有acquire、READY、activation或正向信用操作，健康准备成功仅证明该不可交易的
准备切片。运行时交易、完整credit audit/source/replay、跨片UNKNOWN和生产授权均仍有
独立否决边界；没有真实金融签字或上线GO。
