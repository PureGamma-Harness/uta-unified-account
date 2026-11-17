# CREDIT_BORROWED V2：独立验收参考准备稿

基线`899c91d0a032d88cc4cb8c73ffb09cb2d1bd7236`，独立分支
`test/credit-borrowed-v2-reference`。本稿在读取未来audit/runner/native V2实现前记录已完成
的独立手算与验收观测点。按root紧急槽位安排，常规任务暂停；**完整可执行schema、
Fraction oracle、fault矩阵与实际V2差分尚未完成或执行**，不得把本稿称完整验收。

[五个独立手算快照](../tests/fixtures/credit_borrowed_v2_reference_draft.json)已显式标为
`HAND_DERIVED_DRAFT_NOT_EXECUTED_RUNTIME_NOT_QUALIFIED`，所有runtime观测为null。
它们不是可提交的真实审计档案；原7aa设计、旧golden、此前51项oracle及全部RED保持原字节。
没有SQL/服务/DB/native执行，没有跑负载或读取后续活动实现。

当前首profile仅新建synthetic V2、batch0/cache0、USD/BTC、BTC借款、zero新利息/借款费、
trusted `synthetic_local`，不代表HMAC或外部托管。public/CLI新borrow501保持，已经存在的
PREPARED v1永不promotion解锁；全新V2初始化入口仍须作者明确。opening interest只能来自
真实full-source核验，不能由zero-rate政策抹除或伪造历史decision。

已完成的手算要点：

| 输入/动作 | 独立结果 |
| --- | --- |
| USD100、poolBTC1，借BTC.4 | cash/principal/receivable .4、pool.6；collateral132、loan66、debt40、risk92、IM8、MM4、available84；下一portfolio quote.26，但本片余量仅.1 |
| 上态另有8份乘数1线性挂单@100、IM.1 | reserve80、available4；`floor_.01(4/120)=.03`；借.03后risk91.4/IM8.6/MM4.3/available2.8，.04仍应按原保守quote拒绝 |
| USD−1、BTC1、p.1/i.01、pool.9，借.1 | deficit1另计全价债务；借后BTC1.1、p.2/i.01、pool.8、debt22、accounting88、risk66、IM4.2/MM2.1/available61.8 |
| USD100、BTC.4、p.4/i.05、pool.6，借.05 | gross正好达到allocation.5；利息保持.05，pool.55、risk86、IM10/MM5/available76 |
| USD100、BTC.5、p.4/i.05、pool.6，同币repay.1 | 先息.05再本.05；cash.4、p.35/i0、pool.65、interestcash增加.05；预算释放.1而pool仅增加.05；7腿，不造borrow decision/不依赖market |

负cash的可达蓝图使用zero费preseal线性100开/99平的realized PNL−1，而非改费率或手写
SQL负余额：depositBTC.9→borrow.1→opening interest.01→买单/成交→卖单/成交，账户版本
依次1..7，flat后USD−1；之后新借款版本应7→8。该蓝图尚未实际执行，必须后续从真实
完整journal和base ORDER/FILL档案核对，不能因手算成立就认定source真实。

独立实际验收必须观测而不能由fixture布尔值替代的事实：

1. 原CID/account/kind/canonical business hash贯穿真实inbox、source、intent、credit command、
   专门CREDIT_BORROWED decision、sealed journal及SUCCEEDED terminal，唯一且双向匹配。
   四腿核完整lexicographic集合与ordinal；不能仅核零和或调用generic风险replay。
2. **两段原子性**：first-source与PENDING接纳在producer事务提交，金融rollback后应保留；
   后续loan COMMIT原子绑定这份原source义务、effect/intent/audit/credit receipt/terminal。
   不能虚称已经先提交的source首次INSERT与贷款COMMIT为同一事务。
3. 同实际金融事务读取最新gross正资产、负cash deficits、p/i、frozen、positions、live
   orders/reserve、limits、完整固定allocation及pool，真实版本只推进一次。其他片的未知
   或未用额度不能本片使用；预算仅原币p+i，不包括全部经济债务。
4. 原SID及完整payload绑定初选与末端两次真实检查，保留observed_at/selected_at/last_checked。
   首profile拟要求同一SID；时钟、freshness等号和checkpoint契约仍待作者明确。不刷新
   observed_at，不将检查至物理COMMIT之间暂停/IO窗口冒称硬实时。
5. actual code artifact覆盖新增audit/executor/transition/native及原风险/ledger/dispatch关键
   路径、source与loaded functions/runtime；null或不完整artifact必须拒绝。模板内容hash
   不能代替实际代码身份、认证或资金来源。
6. 新借款原CID成功重试、COMMIT丢reply、重启新owner查询均不得增加loan/journal/decision/
   account-version；unknown不换CID或回收allocation。legacy原receipt只读返回原结果，
   不补CREDIT_BORROWED decision，不伪造此前不存在的durable inbox。
7. 分开注入effects后、完整tuple后、SAVEPOINT rollback、外层rollback、COMMIT后reply丢失。
   已知金融gate失败不能因caller捕获而保留贷款；SAVEPOINT RELEASE不是durable ACK；
   重开核真实持久状态。部分tuple为corruption/HALT，不能补造缺失结果或重贷。
8. REPAY仍需真实source/FIFO/terminal/journal义务，按interest-first生成4或7腿；不造
   borrow decision，不触market。opening利息还款释放p+i预算与pool本金回收分开核对。

正向前尚待明确并补成完整schema/断言的五项：新V2初始化与v1不可升级；双SID检查具体
clock/边界；专用audit格式与artifact覆盖表；legacy receipt无inbox的只读入口；market503/
技术故障对应PENDING、attempt或QUARANTINED策略。尤其PENDING无金融tuple、活跃旧事务
外部只见PENDING、持久partial tuple与读失败UNKNOWN必须分别处理。

下一轮应先以纯stdlib Fraction核对本稿手算、冻结规范化observer schema和完整故障矩阵，
再读作者接口并作只映射字段的adapter，保留每批CPU3 begin/end、命令、source hash及真实
原子结果。内部工程正向GO不关闭HMAC运营权限、loan distress/偿付和生产边界；本稿没有
金融负责人签字、live授权或完整credit audit通过声明。
