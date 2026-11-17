# 0941 transition：原四项离线合同关闭复审

固定作者修复提交`0941c1ac1e9bbafc189979b11e27e5dd5b9175fb`，自有隔离review分支
`review/credit-transition-0941`。`uta/credit_transition.py` SHA256为
`86161437f604cf2c2b19484575bdd3d03bb307b6714a4f28c48ab5dc667efb99`。
**同一份独立原probe实际GREEN退出0，本次只关闭原4项具体离线合同问题。**

没有修改期待来适配实现：执行前后逐blob、SHA256和实际bytes核对原OWN
`7ece8c483571a9ff859f4c71aa1d64402351d90d`的两个文件：

| 原参考文件 | Git blob | SHA256 |
| --- | --- | --- |
| `scripts/probe_credit_transition_reference.py` | `53531ab06ec1b873211a998d72d51b9aac92fbaf` | `aa671dc81ae32b907e708dcb2434325e11f5222c90f7385c52eefb2d0ee0096e` |
| `tests/reference_credit_transition_math.py` | `f88d0e84441d34730ed9f61675e0405cc36de2b4` | `d6026a3b69d25634c82c109205e13799a03ac7950b899a5f136abcb8970aa2db` |

命令只通过原脚本已有CLI更新`--expected-source-sha256`和`--reviewed-commit`，输出到全新
`evidence/runs/credit-transition-independent-0941/`。CPU3只执行一次纯probe，计算0.023750秒，
含启动0.125748秒，subprocess timeout30秒，纯预算3秒；Python3.12.14，无超时、DB、native
或服务执行。没有读取后续活动树或运行作者含tempDB的专项。

| 原block | 相同输入在0941的实际结果 | 关闭判断 |
| --- | --- | --- |
| 合法before version=`I64MAX−1`后，自身after=`I64MAX`不能比较 | 原after/四腿比较成功，`accounting_matches=true`、`operation_authorized=false`；before已经MAX的原负例仍拒绝 | 已关闭原pre/post版本不一致 |
| exact typed descriptor替换两片allocation但保留原canonical/IDs后越原本片额度 | 原`.6 BTC`请求按canonical原本片`.5`以`credit_limit`/409拒绝，与未伪造canonical control一致；不消费替换后的typed assets | 已关闭本反例的离线typed-field信任问题 |
| exact typed expected四腿翻倍而amount/after未变仍输出匹配 | 以`credit_transition_mismatch`/503拒绝；实际从保留primitive重新计算后发现expected不一致 | 已关闭本反例的假expected自洽比较 |
| UNKNOWNasset逸出为无status的policy错误 | 返回本模块`CreditTransitionError`，`credit_transition_invalid`/503 | 已关闭原错误映射遗漏 |

51项普通输入的calculate接受/拒绝、成功结果逐字段/四腿、错误code/status及成功结果比较
均与原独立oracle吻合。6项原postings负控制（乱序、bool ordinal、整数units、带+的单位、
平衡错customer、额外平衡腿）均拒绝503。原低Decimal精度及Inexact/Rounded traps控制仍
完全一致。成功comparison继续全部`operation_authorized=false`。

本次只采用上述原断言，不把作者新增JSON边界或其他专项自动计入独立通过范围。阶梯
quote仍是独立假设手算后给组件的数字输入；没有证明实际SID、freshness、risk/quote档案
或code/source/auth真实性。结构正确的证书、canonical primitive和整数账务一致也不是
live授权、native执行、完整credit audit、物理COMMIT或production GO。

原RED仍在OWN`17ed1b98c1cb72c3bd1bf2d052797d94b929d5c0`及原review worktree保存，
实际bytes再核与原git blobs相同：

| 原始档案 | SHA256 |
| --- | --- |
| `original-red.json` | `c4ead1b4721b598c06de7ca0ff366e05b001091941dea63af5ecaa6ad17f5c91` |
| `original-red-execution.json` | `e2f088bf430f0ac1ba81acd2c3d9aa00ef1746ffce07e9076ed432260a215ee3` |

0941基线没有包含这两个后提交的原RED文件；本组没有删除或覆盖它们，也不将新GREEN
回填原窗口。新的[完整实际结果](../evidence/runs/credit-transition-independent-0941/green.json)、
[命令/退出码/原blob核对](../evidence/runs/credit-transition-independent-0941/execution.json)及
[逐bytes保留记录](../evidence/runs/credit-transition-independent-0941/reference-preservation.json)
均独立保存。没有改运行时、原oracle、旧golden或原设计，没有金融负责人签字声明。
