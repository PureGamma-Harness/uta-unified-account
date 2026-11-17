# M3 独立金融 reference：人工规则先行

本组从旧独立准备稿 `8e6110b830bf09065420068161ce7b7453eaa0c9` 起步，工作树
`/workspace/uta-credit-v2-independent-oracle`、分支 `test/credit-v2-independent-oracle`。
本文件及 [可运行 reference](../scripts/credit_v2_financial_reference.py) 在读取作者未来
payload/capture 实现前记录。只使用标准库整数与 Fraction，不 import 生产 credit、risk、
rounding、replay，也不以生产返回值生成 expected。

当前状态是 **PENDING_ACTUAL_CANONICAL_PAYLOAD_AND_CAPTURE**。人工数值自检通过仅证明
本组手算与本组 reference 一致，不能证明真实 source、SID、UTC 取时、SQL 原子性、
actual journal、FIFO、COMMIT 或恢复。每个向量的这些 actual 字段始终是 null。

## 锁定的人工规则

仅 fresh synthetic USD/BTC、Cross、BTC borrowing、trusted synthetic_local、batch0/cache0；
零新借款费/新利息，已有 opening interest 保留。PREPARED1 永闭，public/CLI 新借款501。
两币都用 10^8 整数单位，绝对 units<10^38，account version 不超过有符号64位范围。
USD/BTC 价格 1/100，默认 BTC 抵押系数.8、USD1，两币 LTV=.5；BTC 借款 IM/MM=.2/.1，
单 USD 结算线性名义金额 IM/MM=.1/.05，乘数1、mark100。借款 step=.01BTC。
风险本金上限10BTC、account本金+利息总额上限10BTC、local asset总额上限100BTC、风险总债10000USD。
全局预算1BTC，固定 shard0=.5、shard1=.5；本地仅可用 shard0，没有动态借用邻片预算。
预算计本金+利息，USD cash deficit 仍按全价计经济债务但不伪装为贷款本金。

保守 portfolio quote 假设新借款所得离开抵押品，用最终债务、E、IM/MM、reserve 的可行性
在整数 step 网格上独立二分；available≥0 且 E>MM。实际 borrow 则把现金与本金同增，
pool 减、principal receivable 增；不重算利息。授权量另受 pool、账户、本地、固定 allocation
约束。repay先息后本，pool只收回本金，利息进入独立 interest cash；不做借款准入或市场检查。
reference 中 repay 后的风险数字仅为人工静态快照报告，不表示还款依赖行情。

全部 postings 由操作和真实金额独立推导；同一 customer 只有一条总 debit。按 account/asset/
units 的 lexicographic 顺序编号 ordinal；borrow4腿、混合还款7腿、单种还款4腿。检查逐币零和
不能替代逐项 account、方向、金额、ordinal、实际原 journal hash 的核对。

## 八个人工向量

前五例沿用原准备稿的独立输入，但在本组实际运行独立计算，后面三例增加组合边界。

| 向量 | 输入、动作与手算 after |
| --- | --- |
| M1 | USD100、poolBTC1，借.4：BTC cash/p/recv=.4、pool.6，collateral132、debt40、accounting100、E92、IM8/MM4、available84；下一风险quote.26、本片授权.1，4腿。 |
| M2 | USD100、cash/pBTC.4、pool.6，未成交线性买8@100，reserve80，借.03：collateral134.4/debt43、E91.4、IM8.6/MM4.3、available2.8；下一quote/授权.02，4腿。原态.04虽然事后可用仍正，超过保守原quote.03而拒。 |
| M3 | USD−1、BTC1/p.1/i.01/pool.9，借.1：cashBTC1.1、p.2/i.01、pool.8，cash deficit1、debt22、accounting88、collateral88、E66、IM4.2/MM2.1、available61.8；下一quote/授权.22，4腿。 |
| M4 | USD100、cash/pBTC.4/i.05/pool.6，借.05：cash/p.45、i.05、pool.55，collateral136/debt50、accounting95、E86、IM10/MM5、available76；下一风险quote.18、本片授权0，4腿。 |
| M5 | USD100、cashBTC.5/p.4/i.05/pool.6，还.1：cash.4、p.35/i0、pool.65、interest cash+.05，collateral132/debt35、accounting105、E97、IM7/MM3.5、available90；释放预算.1、pool只增.05，7腿。 |
| M6 | USD100、BTC1.2/frozen.2/p.2/i.01，BTC阶梯前50USD×.8/之后×.5；多.3BTC-PERP/cost27；买2已填.5@105、另 reduce-only卖.1@90。reserve=15.75+7.5+1=24.25，原抵押165/E147/IM7.2/MM3.6/available115.55，借.01后抵押165.5/debt22、accounting202、E146.5、IM7.4/MM3.7、available114.85；下一风险quote.60/授权.28，4腿。 |
| M7 | USD100、cash/pBTC.4、i0/pool.6，还本金.1：cash/p.3、pool.7、recv.3；抵押124/debt30、accounting100、E94、IM6/MM3、available88，4腿。 |
| M8 | USD100、cashBTC.5/p.4/i.05/pool.6，还息.02：cash.48、p.4/i.03、pool.6、interest cash+.02；抵押138.4/debt43、accounting105、E95.4、IM8.6/MM4.3、available86.8，4腿。 |

## 暂未映射的真实规范

本组 owned observation schema 不是作者的 canonical payload 格式。真实 contract OWN 到达后，
只映射实际字段，不将它的 self-reported expected legs 当作独立 journal。必须从原 receipt
引用的 ledger event 及按 ordinal 查询的 postings 取实际行；真正的两个 UTC 时间与原 SID
也只能来自真实执行。source+PENDING 的 producer COMMIT 先于金融 COMMIT；金融回滚不能
删除已接纳 source，不能把两次 COMMIT 虚称一次。

完整 capture 必须覆盖：gross/负cash/p/i/frozen/orders/positions/tier；account/local limits；
完整global/static allocation；pool/receivables；before/after versions；原CID/source/SID；
真实两次检查；journal原head/hash/ordinal legs；intent/decision/credit receipt/terminal；
producer/financial事务边界及重开状态。predicate计算通过不替代实际SQL观测。

范围仅纯 reference。未接任何 production capture，未执行真实 positive 写入、DB、服务、
网络、压力或原jobs SQL；不修改 M3/runtime、冻结工作树或历史证据。回滚只需 revert本组
新增代码/文档/证据；生产、10k、HA、HMAC和贷后处置均没有验收结论。

## 后续合同对接与已运行范围

先行 oracle、八个人工输入/常数及第一次运行已锁为
`2b83a47`，首次执行 exit0、0.049194秒；其原字节没有覆盖。之后才阅读作者已提交的
`52207b6075dce8662bf951c89015415e4fca495d` 两个 contract blobs，继而阅读补明确的
`b510d18cb4ea6ab6213374884fa40a2f7754977e`，均不 import 生产模块。两个合同版本的
原文件及 SHA256 保存在 [证据目录](../evidence/runs/credit-v2-independent-oracle)。
没有读取未提交的 capture/audit 核心，也没有运行作者未来 positive pipeline。

b510 明确 account_limit/local_asset_limit 均按 gross本金+利息核对。本组去掉原准备稿
中与同数值 gross gate 重复的 account本金gate；风险规则的 max_principal 是另外的门槛，
继续单独保留。八个人工结果不变。这是接口语义对接，不能称为生产缺陷或生产修复。
新 reference 同时显式保留负的本金/利息 ledger余额，验证其与分开的正债务一致，验证
本片 aggregate p/i 与两种 receivable 一致，并输出 before/after 四组 gross components。

依照 b510 的独立 journal 算法：fingerprint 是 canonical
`[[account,asset,整数units],...]` 的 SHA256；event hash 是 canonical
`[sequence,event_id,previous_hash,fingerprint]` 的 SHA256；credit event ID 是
`credit:sha256(canonical(['account:'+account_id,CID]))`。逐条 journal 比较从操作与原 before
计算 expected legs，不读取输入中的 expected-postings。单测使用另一份手写四腿常数；
把 pool 账户改成 interest cash、保持零和并重算全部 self hash 后仍会因金融腿不一致拒绝。
函数返回 SQL/COMMIT provenance=PENDING，内容 hash 一致不升级为实际事务证明。

另外核对 source canonical text/原 command hash/关系字段/content ID、canonical整数单位、
重复字段/float/bool/未知字段/overflow、原CID的FIFO次序、两次UTC年龄等号/1微秒越界、
SID变更、回拨、limits/pool/allocation独立约束以及 halt 且风险额度0时的 market-NONE还款。
这些是 reference 的输入拒绝和 predicate 检查，**不是生产门禁拒绝验收**。完整 bundle/
artifact/policy/catalog/receipt 的实际适配，以及 pool-funding 原账、intent/terminal、丢reply/
restart/unknown/SAVEPOINT/双COMMIT 的独立观测仍待 actual capture，不能以本组通过补齐。

最终18个 reference tests 在 CPU4、每条命令30秒限时下均实际通过：

| Python | 测试 / 进程墙钟 |
| --- | --- |
| 3.10.22 | 18项，0.045 / 0.100秒 |
| 3.12.14 | 18项，0.031 / 0.134秒 |
| 3.13.5 | 18项，0.030 / 0.110秒 |

此前14项的中间原始记录也保留，未覆写。所有阶段均无 red；没有伪造红态或生产 bug。
仅本地 reference 自检 PASS；CV2-01..12 的 actual positive 总体状态仍是 PENDING。
