# M3 static certificate：独立金融验证准备

基线 `aa72a953bcbe5fd809b1b159a751d152afedb5d9`，隔离分支
`test/credit-certificate-reference`。此提交先冻结独立语义oracle和向量，未阅读或调用尚未
交付的生产`credit_policy`实现。oracle使用已发布设计的document envelope，不宣称是新生产
API。后续adapter必须映射含义，不能调用生产的hash/整数/求和/校验helper生成expected。

现有参考结果：108个明确标注的证书向量、4个raw JSON边界，5项纯参考测试通过。输入来自
原canonical design fixture，未改原设计、旧golden、`uta/`、NEXT/M2或任何运行中的authority。
所有数值均为小量整数计算，没有SQL、服务、重负载或客户资金。结果见
[原始证据](../evidence/runs/credit-certificate-reference/reference-pre-api.json)。

独立不变量包括：

- 原币unit必须为canonical ASCII整数串，非负且小于`10^38`，禁止int/bool/float/空白/
  科学记数/Unicode数字/分数/溢出；格式、版本、scale、shard为确切整数而不是bool。
- 使用无界整数重算`Σallocation<=global`及`opening principal+interest<=allocation`。
  不可用float、SQLite REAL/CAST或有符号64位截断。正控制包括`2^53+1`、`2^63+1`、
  `10^38−1`、opening利息等号、未分配global余额和pool总额不等于预算。
- 完整证书须覆盖精确的全部shards，拒漏片、重复shard/authority/source、错asset/scale/
  authority/layout/policy/version/budget身份。上下文的预期identity来自独立的封存值，
  不能从被修改的候选证书重新导出。
- hash/canonical bytes损坏单测之外，还把修改后的所有内容ID和引用重新计算，再验证外部
  identity不符仍拒绝。内容hash证明字节，不证明资金、认证或该证书就是已封存的那一份。
- 静态合法的另一分配`(0,1)`不等于允许替换封存的`(.5,.5)`。UNKNOWN可能已经提交的贷款
  不消失；重算全部hash也不能解除sealed certificate identity。此历史属性最终必须由真实
  installer/load持久边界执行，纯无状态validator无法独自证明。

原始JSON重复键和非标准NaN/Infinity在字节入口单测，不能把已经解码成dict的对象API冒称
覆盖了重复键。零global/allocation是否允许、identifier语法、unknown fields/ordering及版本
范围原来属于wire选择，已在向量中单列，不在接口提供前冒充已确认漏洞。后续接口给出的
USD scale2..8、其他scale0..18、version1..I64MAX等范围，将单独加入生产形状参考向量。

生产接口公布的新义务还须独立新增：policy/certificate资产集合完全相等；完整authority表；
每片每资产funding claims有序且正数；同一source reference全certificate唯一；同一
`(shard,command_id)`跨asset唯一；pool不超过其funded quantity，funded总和也不溢出。
资金claim仍是static内容，实际ledger中的source所有权、opening水位及不可变性需要native
安装时重读核验，不能由claim自述推断。

真实差分待生产提交后进行，先记录不可变源码及运行时，再比较实际接受/拒绝及返回的精确
单位/IDs，而非只比较异常文本。任何错误DDL、OperationalError或未执行native调用都不能
当成功拒绝。发现差异保留原输入和实际错误，先解释契约再决定是否为blocker。

native否决矩阵尚未执行：

| 场景 | 必需结果 |
| --- | --- |
| 无credit cap的base/batch | 保留原owner/原业务能力，不因新default-off代码误杀 |
| 合法完整证书、仅`NATIVE_PREPARED` | 实际owner acquire、READY和activation均拒绝；无新金融成功 |
| 缺实际audit/source/artifact/replay | 不得用synthetic source、null artifact或dummy cap放行贷款 |
| 不完整/错hash/错identity/超额证书 | 第一个不可逆安装步骤前拒绝；不能仅由后续Python入口检查 |
| 封存后换证或UNKNOWN片额度搬迁 | 持久identity拒绝；不按可见PENDING/读失败回收真实可能已用额度 |
| actual integer/native legs差分 | exact amount↔units、borrow四腿、opening-interest repay、错account/asset/ordinal、漏/额外腿、已有债务UPDATE/DELETE、catch后COMMIT均另验 |

这不是dummy cap放行正例、真实资金或上线GO，也不是金融负责人签字。M3工程授权不改变
本轮`NATIVE_PREPARED`不能取得写者或产生新金融成功的边界。

## 生产wire公布后的独立标准例

在仍未阅读生产实现时，按作者公布的`validate_native_descriptor`字段合同另写
[descriptor oracle](../tests/credit_descriptor_reference.py)与
[157项新标准例](../tests/fixtures/credit_descriptor_reference_v1.json)，保留前108项设计语义输入
不动。参考仍自行实现严格shape/type、整数求和、canonical hash和外部expect绑定；只复用
本组已锁定的ASCII整数语法及`10^38`范围oracle，没有生产imports。

新向量覆盖：top/policy/cert/claim多层精确字段与bool/float拒绝；USD scale2..8、BTC0..18；
version至I64MAX；policy资产集合与cert相同；全局source reference唯一及同片command ID
跨asset唯一；正funded_units、funded总和边界、pool<=funded；hash全部重算后外部expect仍
拒绝错配；sealed cert不替换。正控制含零allocation/global、零pool空claims、其他片相同
command ID合法及大于64位的原币数量。完整funded claim仍不代表实际到账或ledger核验。

allocation数组重排另标`wire_order_pending`：公布接口明确funding claims排序，却尚未说明
allocation是否必须排序。若生产选择固定顺序，应先记录为wire契约补充，不能把它冒称
算术漏洞。`expected_authorities`在reference中为发布的完整列表；若实际API采用mapping，
adapter只转换容器、不改变独立的shard→authority意义。

本轮1个小unittest枚举157项，0差异；[原始记录](../evidence/runs/credit-certificate-reference/descriptor-reference.json)。
这是与本组oracle比较，尚未与生产函数差分，也没有native或SQL执行。
