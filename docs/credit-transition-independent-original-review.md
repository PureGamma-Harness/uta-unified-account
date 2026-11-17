# 23efd offline gross transition：独立原始审阅

审阅对象固定`23efd5f4121ea7509a544741d3e0a2fe98be50ea`，
`uta/credit_transition.py` SHA256为
`8423116055adc885077ac920d0ca135dffeb8738197a059d61fe53c2ef1728e0`。
独立整数/Fraction oracle与安全assert先锁定在OWN
`7ece8c483571a9ff859f4c71aa1d64402351d90d`，再运行真实纯函数；未读作者随后未提交树。
**原probe实际RED退出1，存在4项离线合同问题，阻断未来audit直接信任本版本输出。**

CPU3、Python3.12.14，51项普通case的calculate接受/拒绝、逐字段整数/四腿和错误码/status
均与独立oracle吻合；其中一个合法calculate结果自身compare失败，另有三个独立安全/
错误合同assert失败。纯计算0.017941秒，含启动0.157425秒，timeout3秒。没有DB、服务、
native、owner、READY、activation或资金变更；没有重跑含真实tempDB的作者11项测试。

四项原始失败：

| ID | 最小输入与实际事实 | 分类及要求 |
| --- | --- | --- |
| `version_last_advancable_roundtrip` | before version=`9223372036854775806`合法；calculate产生after=`9223372036854775807`且所有账务正确；compare自己的完整after/四腿却报`credit_transition_invalid`/503 | 确定的pre/post边界不一致。post-state合法并不要求还能再次advance；应把可推进pre版本与已完成post版本校验分开。 |
| `forged_exact_descriptor_immutable_budget_changed` | 从真实parser结果用`dataclasses.replace`把两片allocation由`.5/.5`改为`1/0`，typed分配总和仍等于原global1，canonical payload及descriptor/certificate IDs不变。实际calculate接受`.6 BTC`，越过原本片`.5`；同一请求使用原canonical parsed control正确拒`credit_limit`/409 | 离线pure入口把exact-type等同“内容已解析且一致”，caller合同不足。typed dataclass是声明，不能充当不可伪造seal；应重新核对canonical primitive与实际typed字段。没有执行native；native现有raw→validator边界不是本反例的捷径。 |
| `forged_exact_expected_double_postings_unchanged_delta` | 从真实calculate结果用replace仅将四腿由±`.4`改为±`.8`，amount仍`.4`且after仍cash/principal`.4`、pool`.6`；向compare提供同一伪造expected的wire。实际返回`accounting_matches=true, operation_authorized=false` | 离线comparison可以被“两边同时错误的expected/actual”欺骗，连四腿与自己的before/after/amount都不一致。exact-type不能证明expected由原primitive计算产生；必须从保留的primitive重新计算并核整个结果。仍无授权或物理journal真实性主张。 |
| `unknown_asset_transition_error_contract` | 已合法parsed descriptor，请求asset=`UNKNOWN` | 实际抛`CreditPolicyError(code=credit_allocation_missing,status=None)`，未遵守本模块公布的typed输入`credit_transition_invalid`/503。属于内部错误映射问题，不是接受未知资产或新HTTP漏洞。 |

前两项caller伪造反例没有声称绕过真实native descriptor重验、SQL guard或公开borrow501。
本模块始终是unwired纯组件；第三项实际成功comparison也明确`operation_authorized=false`。
当前问题是未来数值audit若只信这些typed对象，会得到错误的静态budget/账务匹配结论。

独立算术范围与正/负控制：

- 从四个owner的double-entry movement推导cash、negative principal liability、pool与gross
  principal receivable，再由owner余额重建post-state；不调用生产transition/整数parser来
  产生expected。原`.4`案例得到customer/principal/receivable`.4`、pool`.6`、interest0。
  原001的独立快照再借`.11`超过`.5`约束而拒，借`.1`恰到`.5`可行。
- 本金`.2`、利息`.01`时，借`.3`使gross `.51`而拒，借`.29`恰到gross`.5`；正cash不会
  净掉principal/interest，负cash也独立保留。其他账户占用本片gross/receivable后只剩
  本片余量；其他片未用或失联额度不会进入本计算。快照是给定账务输入，不声称其历史
  source/funding chronology已经由本组件证明。
- pool、给定quote、step、account/local/allocation约束分别校验；canonical ASCII units、
  bool/float/非法字符串、负债/应收不协调、38位cash上下界/overflow和版本分别覆盖。
  Decimal精度1且Inexact/Rounded traps开启时结果仍完全一致。
- 假设阶梯例：USD100、BTC cash`.65`、本金`.4`，BTC前USD25 haircut`.9`，剩余USD40
  haircut`.6`，BTC price100、LTV`.5`、借款IM`.2`。Fraction算得collateral146.5、loan73.25、
  debt40，LTV bound`.3325 BTC`，按`.01`向下给出quote`.33`。本probe仅验证组件消费给定
  `.33`并拒`.34`；没有真实market SID、freshness、code/policy archives或quote authenticity。
- 对真实且未伪造的expected，六类postings负控制全部拒绝503：乱序、bool ordinal、整数
  units、带+非canonical单位、平衡但错customer、额外平衡腿。这与伪造expected导致的
  自洽假象分开，不将其混称为所有posting校验都缺失。

所有输入、independent expected、actual返回/异常、四项failed safety IDs、源码全SHA及
原traceback保存在：

- [original-red.json](../evidence/runs/credit-transition-independent/original-red.json)
- [original-red-execution.json](../evidence/runs/credit-transition-independent/original-red-execution.json)

可重用的[原oracle](../tests/reference_credit_transition_math.py)和
[原probe](../scripts/probe_credit_transition_reference.py)字节不改；后续作者另OWN修订后，可
显式提供新source SHA及commit，输出到另一个GREEN文件进行同原probe复审，不覆盖这里的
原输入、原期待或原RED。源码、root金融reference、旧golden和原设计均未修改。

本结论没有放行完整credit audit、quotation/risk重演、资金/认证/source真实性、native操作、
COMMIT或生产，也没有虚构金融负责人签字。
