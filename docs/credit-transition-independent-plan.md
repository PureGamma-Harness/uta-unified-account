# Offline gross transition：独立最小语义参考计划

本组固定源码`23efd5f4121ea7509a544741d3e0a2fe98be50ea`，只读生产模块；另写无任何
`uta` import的[整数/Fraction oracle](../tests/reference_credit_transition_math.py)。独立oracle
从四个owner的借款分录推导状态，不调用生产估值、整数parser、gross transition或serializer。

53项左右小输入覆盖原手工.4、再借.11、.5等号、本金+利息口径、负cash、他户本片占用、
其他片额度不转移、pool/quote-input/step分别限制、38位上下界、metadata版本、非法类型及
Decimal低精度。一个假设阶梯抵押例用Fraction算得给定quote .33 BTC，再验证此组件消费
输入quote .33并拒绝.34；不声称真实行情/版本/风险报价已复算。

冻结安全断言包括：

- caller用`dataclasses.replace`改变exact-type descriptor的两片分配，保留原canonical
  payload和IDs且分配总和仍等于global，不能使本片越过原已声明.5而得到.6的离线准入。
  这是pure caller合同，不是native raw→validator边界或线上授信。
- 合法before version=`2^63−2`推进为`2^63−1`后，比较自己的完整after及四腿应一致；
  post-state有效不能被误当成仍需再次可推进的pre-state。
- exact-type `BorrowTransition`的postings被替换为双倍金额、而amount和after未变时，
  comparison不能因caller两边同时错写而输出accounting_matches。
- 真实expected对乱序、bool ordinal、整数units、带+非canonical units、错customer、
  额外平衡腿应拒绝。typed输入错误/mismatch为503，quote/gross/pool业务不足分别为409；
  unknown asset也应遵守模块公布的typed input错误契约。

[实际probe](../scripts/probe_credit_transition_reference.py)只调用纯policy parser和纯transition，
不构造服务/数据库、不调用native/owner/READY/activation。CPU3纯计算限3秒。先保存raw，
再执行真实安全assert；如有差异保留RED，不改生产或预期凑绿。后续作者新OWN只能通过
显式提供新源码hash和commit重跑同一oracle/probe，原始bytes及红态另存不覆写。

任何成功comparison都必须`operation_authorized=false`。这不是完整credit audit、source
真实性、外部资金、quotation replay、COMMIT或上线GO。
