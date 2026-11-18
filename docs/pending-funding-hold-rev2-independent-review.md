# Pending funding hold rev2：独立规格复审

固定审查提交 `8008a0b24e8dc0095420b18f6b154c9db655a183`，parent 为原独立审查 `ade10972b8044e3c753113970db34b3c85950ca4`。结论：**B1/B2 的规则定义补救与新增人工算术可接受；没有新增 D0 定义阻断。D2 仍为 BLOCKED，未获金融执行批准。** 最多可另行审查 D1 纯 hold 算术/规则模型子集及其精确源与执行计划；本报告不给执行 GO。

机器证据见 [review-8008a0b2.json](../evidence/reviews/pending-funding-hold-rev2-independent/review-8008a0b2.json)。本轮只读取数据与不可变 Git，使用标准库 Fraction 从合成十进制字符串独立复算；没有目标 import、编译、测试、SQL、进程探测、worker、CI或网络动作。没有复用生产金融核心函数或修改作者文件。

## 原件、引用与覆盖

五个修订文件的物理/Git字节一致，变更范围仅文档和JSON。原17例、原13项 source pins 与 ade 两份审查文件保持原字节；manual/source 文件同时与原 `bac842516abc8f1e8af42f8624b5cf28f31b5972` 核同。13项源码的 commit、blob、字节数、SHA-256全部核对一致。这是静态引用闭合，不是加载运行时或执行证据。

规则矩阵含25条规则、32个门槛、12项不变量，case/test 引用全部解析到声明对象；32个门槛仍为 NOT_RUN。原报告的 B1/B2 否决记录没有重写。本报告只对固定 rev2 的补救定义作新结论，不把原基线或任何未运行门槛追认为通过。

## B1：稳定义务与唯一 active representation

`duty_id` 在 schedule/cut 前由明确 canonical 字段确定。exposure、cap、final cut 为分别 typed 的不可变内容引用，不再充当经济主键；claim、任务ID、价格/数量/费率与源码SHA不改变既定义务身份。

hash字段包含 interval 和 rule scope，但独立 natural-slot 唯一约束排除它们。因此更换两者虽然会生成另一个 hash，**仍必须因同一自然slot冲突而拒绝**，不能建立第二债权。这一点不能只靠hash去重，也不能只靠内存检查。固定产品日历/批准规则版本仍是新slot合法性的前置，不能借制造额外period绕开日历。

每duty唯一active阶段、revision/CAS、预期cap/exposure引用及同事务转换定义清楚。U→P/N/zero时旧内容保留为consumed历史，新贡献与版本/完整basis一起提交；崩溃只应看见完整旧态或完整新态。M19正负/零解析均没有U与P重复占用或N提前信用。并发约束、唯一索引、历史watermark重建及故障原子性仍未执行验证。

## B2：真实冻结、先行成交与支付顺序

本次选择的规则能同时保留义务和 `frozen<=gross`：先履行影响backing的已确认成交及费用，再按最新cash、allocation lineage与版本检查 `F_after<=max(C_after,0)`。资金费不能用自身H否定付款，但也不能改写其它真实冻结；只消费本笔已清偿P/H，其它duty的H继续占用。其余资金费H是风险占用，不应误作另一份真实spot冻结或重复会计负债。

backing不满足时，due P/H、N、限制、首次期限、phase与幂等outbox一起持久提交；没有cash腿、hold释放或APPLIED。真实取消/成交确认才能改变F；终态文本、请求、超时、运营点击或重启均不是释放证明。真实释放与付款是两个可区分的已提交事件，释放后仍须处理先行确认成交并重取版本重算，不能凭旧投影付款。

F为零时允许原M05/M16的负现金：记录cash deficit，不能造本金、第二次扣H或免债。M25同时验证另一笔P10保留，未被自身付款顺便消费。完整本地period一个payer等待时，其他现金腿及receiver信用一起等待；N只保留应收，不成为风险抵押或借贷池。

## 新增十例独立复算

105个显式数值字段比较全部一致；M18的canonical JSON与duty SHA另行独立计算。下面为主要结果，**不代表状态机或金融接口已执行**。

| 案例 | 独立结果与限定 |
| --- | --- |
| M18 | canonical duty digest符合；改变scope/interval的natural slot不变，必须由持久唯一约束排斥第二义务。 |
| M19 | U6替换为P2.46，释放3.54；或N2.46/H0、完整zero阶段。两份贡献同时存在会错误成为8.46。 |
| M20 | 100/F95/P12先WAIT，risk=-7；确认释放10后100/F85/P12，risk3；付款88/F85/P0，risk仍3，payer应计始终88。 |
| M21 | 先成交成本4+费1、消费原锁4：cash95/F91，risk=-8，应计95+资产4-P12=87；再释放10及付款后risk2，应计仍87。 |
| M22 | 不完整CANCELLED回复不能释放F95或付款，P12保留。这里只复核其数值/规则前提，不执行ack适配器。 |
| M23 | 首次wait0+30s得到deadline30s；20s重启不变成50s。4次查询若从0按5s间隔发出，可在15s先耗尽预算进入review；到期点取先发生的边界。 |
| M24 | 仅区分100/95/P12等待、100/85/P12真释放、88/85/P0支付；88/F95违反backing。已付后仍保留**同一笔**P12会双计；别的duty H应继续保留。 |
| M25 | 3/F0付5到-2，gross正现金0、F0、deficit2、P0；另例F1未释放不能付，确认F0后付12到-7，另一P10保留，risk=-17。 |
| M26 | 真实独立资本7须有source-7/customer+7，付后cash95/F95、risk0；MM0等号仍不安全。若为贷款，principal7保留，risk为-7而非0，未获自动借款能力。 |
| M27 | A受阻时整期不付，B与receiver不预先入账；A确认释放后88+42+20=150，与原100+50+0守恒。 |

资金费等待、冻结释放和P/N消耗不重复改变财富：P/N在义务子账确认，应计为原cash-ledger权益-P+N；H=P+U仅为风险占用，U不是确定应付，N不是抵押。实际支付减少cash与P同额，应计不再减一次；收款增加cash与减少N同额，也不重复增益。M21唯一额外财富损失是成交费1。资本/债务替代能力仍不支持；其算术例不是资金来源、权限或入账证明。

## 有界等待与多义务并发的实施门槛

wait policy必填、严格版本化、无默认；first-wait起算、持久high-watermark、deadline与query预算不能随claim/重启/新请求延长。先耗尽任一边界就DEFAULT_REVIEW，P/H/N与限制不消失，late ack只增加事实，不能自动解锁。**有界的是自动WAIT，不是承诺缺ack/资本时付款必在期限内完成。** 缺少外部事实时进入人工恢复是本系统选择，不是债权forfeit，也不是无条件无死锁证明。

多个duty请求同一allocation应共享稳定action identity，实际释放只发生一次；各自P/H和deadline分开保存。每笔付款必须在前笔实际cash/锁变化之后重取版本，不能用同一释放额或旧cash快照授权两笔。查询attempt的持久计数、共享action的政策归属、未知结果是否消耗预算，以及禁止新duty/claim重置预算，须在D1状态模型或后续代码审查中明确并验证，不能让实现自行取最大预算或重新起算。当前文字已声明去重/不重置不变量，本轮没有执行并发模型或证明数据库实现。

下一阶段必须保留并具体化以下验收：自然slot/active唯一约束与双resolver CAS；wait/outbox原子性；真实cancel/fill watermark与allocation来源；先行确认义务的受限权威opener；逐边界崩溃、原ID查询与重开；多duty共享动作和期限；完整period/应计/分录守恒；旧writer与无hold入口排斥。源代码、权限、参数和执行资源分别另审，不能从105个Fraction比较推导这些门槛已通过。

## 发布决定与回滚

无新增 D0 定义否决项；B1/B2补救可作为后续纯算术/规则模型的受审输入。**D2无条件保持BLOCKED**：现有基线没有可靠cancel/fill-ack、持久outbox、先行履约opener、完整版本fence及真实事务/重开证据。全账务应计映射、数值全域、金融签字、撮合、容量、灾备及真实资金审批也没有由本报告关闭。

本次只新增两份独立审查文件。回滚删除/revert本审查即可；保留rev2、原17例、13项pins、ade报告及全部历史义务/账务。没有部署、迁移、金融操作、目标试跑或网络动作。
