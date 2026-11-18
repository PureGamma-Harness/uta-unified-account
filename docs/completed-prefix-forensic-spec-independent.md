# 完成前缀取证：独立规格与手算审查

固定审查提交 `19f4b5d3981688898bd221a9af128c9cf768eab6`，范围为其 5 个新增规格/schema/算例/计划/来源文件。**没有阻塞纯 contract/reference 实现的规格矛盾；实际 audit 仍被未证明的全 writer 静止与一致物理输入前提阻塞。** 本签署仅为规格与手算审查，不是金融规则签字、实际方法验收、执行 GO 或生产审批。

## 手算核实

N=3、K=2 时借款本金 6 satoshi、累计归还 4、剩余 2。每 fill 费用 40,000 USD 最小单位；每交易客户两轮共四 fill，费用 160,000，客户各余额 99,999,999,840,000；system fees 为 320,000，credit USD 为 100,000,000,000,000，custody USD 为 −300,000,000,000,000。五项 USD 分量和为 0。

BTC 分量为客户 100,000,002、pool 99,999,998、本金负债 −2、本金应收 +2、custody −100,000,000、capital −100,000,000，六项和为 0，剩余本金负债仍须单列 2。没有净额清零或把原计划 N 偷换为 K。

两轮期望 8 orders、8 fills、4 matches、2 partial cancellations、12 account commands、16 risk decisions、6+5×2=16 ledger events，零开放订单与仓位，与固定合成规则相容。这是手算核查；没有执行纯参考器、读取原任务数据或生成实际 forensic receipt。

## 契约与实现条件

原 strict producer audit、completed 终态 gate 和原 receipt 不变；新模式固定 paused、1≤K<N，只能使用原唯一连续 DONE 前缀。不得舍弃 K+1 已接纳/在途义务、未决 step/fault 或未知行动。所有 control lane 的 bootstrap、feed、halt/activation 也必须逐一找到来源；无 account_id 不能成为忽略理由。单纯订单、账务或 command 总数相等不能代替唯一 ID join 与全部原始分录守恒。

先证明 quiescence，再进行 SQL/backup 的政策正确且可 fail closed。当前没有覆盖全部潜在 writer、旧主恢复及跨库水位的实际证据；PID 消失、driver exit、lease 过期或审计进程自身只读 namespace 都不充分。未证明此前提时拒绝开启 SQL 是预期结果。非空 WAL 不可用 immutable 打开后假装完整；无法保证原库/sidecar 不写入或无法得到完整一致的私有输入时也必须拒绝。这些是后续实际 audit 的门槛，不由 schema 或手算通过替代。

纯 validator 的权限必须与执行验证器分开：调用者提供全 true checks、自算 manifest SHA 或声称 GRANTED，只能形成待验证的 receipt 数据，不能让纯形状/公式校验器新发实际 `PREFIX_VERIFIED`。纯阶段应返回“契约有效但未执行/未独立认证”的结果，并保留 checks 的证据来源、审查绑定及真实执行 witness 的缺口。只有后续明确授权且独立验证全部实际数据的阶段才能产生所声称的执行证明。

v1 schema 已明确只是输出形状；严格整数/bool/float 差别、K<N、规范 birth、来源真实性、完整 control 归属、全分录重建与 snapshot 水位必须由实现验证。所有资格 false 及独立 receipt 类型有助于隔离原六小时验收，任何新 prefix 结果都不能升级旧 NO_GO。

## 证据、部署与回滚

本次只读 Git/source/spec，固定五文件 SHA 和人工核查结果见 [审查记录](../evidence/reviews/completed-prefix-forensic-spec-independent/spec-review.json)。未执行测试、SQL、audit、clone、observer、信号或读取原数据。新 OWN 仅增加此文档与独立记录，不修改作者文件、运行源、schema、风险配置或服务。撤销本 OWN 只移除新增审查材料；原失败、原数据、原 NOT_RUN 和全部执行门槛保持不变。
