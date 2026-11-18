# Independent Fraction reference V3：完整导出的有限 CODE 审查

固定源码 C `7975266d1f336974ce90b73c5ab0706532a4dcd9` 与清单 F
`cab03a380d1bac48eebd398d7ba77a912bc6517c`。结论为
**CODE_CLOSED_FOR_V3_SUPPLIED_DATA_REFERENCE_SOURCE_NOT_RUN**：在声明的11文件
及必要公开规则/旧自身源范围内，未发现当前 V3 supplied-data 参考的阻断缺陷；
原 RV2-B1 的最终 lineage 表示在新 C/F 中获得前向静态闭合。旧612、04df的
BLOCKED/NOT_RUN原义完整保留。本结论不批准金融结果、一般codec、全样本、
差分、资源或生产，也不给任何执行GO。
机器记录见 [review-cab03a38.json](../evidence/reviews/funding-hold-reference-v3-independent/review-cab03a38.json)。

## 固定导出、来源与隔离

在 `/workspace/uta-funding-hold-reference-v3-fcab-code-review`，branch
`review/funding-hold-reference-v3-fcab-code`，基于F独立建worktree。F的parent确为C，
唯一变更为source-manifest.json；C的parent确为d358。C tree
`e413d0cfb3b9f2e47c9c3f393cabfe316b0b7b24` 与清单一致。十个非manifest blob由C
固定，F补20984B/SHA f98e53481f7d4bec1121dc06c0bfdceeddcf0370812b170821d992e235f7a1eb
清单，以F不可变commit避免循环自hash。public-export为3302B/SHA
27909eb345f7f8c14f655681cffd3b893bd4e4ef462eb05d6f3af5116e3b68b2。

完整阅读参考581行、generator442行、测试575行及声明的全部元数据/manual；
11文件合计168678B，物理bytes与F Git全同，十项C pins均匹配。wire33268B/SHA
6dd60f660a9a16c836b3572c7183d5a2085f2ff3ffae82fa66c7d4bdbf2b3bcd，
逐字节等于此前完整读取的d358公开V3合同。旧e6/V2的22工件219896B逐项Git/
length/SHA相同；新manual13853B/SHA
930cc07f583f2ad5b0a51084a15005f50981293ecd16e0b38e0618790348994c
与e6原blob逐字节相同，测试仅用新v3数据路径，未形成旧程序依赖。

读取遵循128MiB/512文件预界。逻辑固定集合为11新+22旧+13公开pin记录，
共46条/573818B，无archive或全库内容扫描；重复展示/AST/哈希读取也在预界内。
只读取8008/895的公开规则/类型资料、2bb与86、69与54af及旧04df来源。未读取
生产financial core/DTO validator/helper/builder、目标算法或运行答案来构造oracle。
参考仅依赖datetime/Fraction/hashlib/json/math/re；generator仅hashlib/json；测试
仅自身两模块与stdlib。AST imports、接口signature及7-key case wrapper与manifest/
export相同，无动态exec/eval/import/compile入口。作者未读生产算法为给定provenance；
静态依赖检查不声称取证了作者全部历史文件访问。

参考分支的uta tree只作Git身份检查：F/C/d358均为
`9f20f2f204cde57e6b03a6722957584457d99aff`。未读其算法，也不将这棵参考工作树
误说成root当前public67 runtime的同一tree或功能验收。

## RV2-B1 在新固定源的前向闭合

`_stage:208–232` 对final要求另有typed FINAL_CUT，并要求E/C同时null或同时
为完整typed同duty/rule-scope ContentRef。`_allowed_step:235–245` 再判上下文：
registered→P/N/zero仅允许两项null；U→P/N/zero要求完整E/C与先前U逐字段相同，
并保留amount<=given cap。`_state:248–265` 验证history≤2、revision=len(history)、
每个stage合法、registered起始和每个allowed step，故不能以无上下文final shape
绕过历史链。final无后继，APPLIED仍UNSUPPORTED。

`stage_advance:445–462` 先验证提供state/proposed/expected，要求完整expected
Stage的kind/amount/三refs及revision同时等于current；随后验证allowed step，
复制原state、append实际旧active、替换proposed并重验整个new state。没有补refs
或清空旧负例。legacy单引用保持明确UNSUPPORTED。部分pair、missing both、
changed E/C、foreign duty/scope、缺final、无U却带lineage、历史与当前不一致、
stale CAS、cap breach和final mutation各有当前源的拒绝路径。

聚合`286–310`仅取`state.active`的kind/amount，历史U与保留refs无贡献；因此
公开给定U600→P246的active P246/U0/H246，转N246为N246/H0，zero无贡献，
不会因保留E/C多占一次U。这是源与公开规则的静态推导，不是执行结果。
同一current/history整体自洽地被替换，D1无法认证；typed shape/相等hash不证明
内容真实性、批准、真正历史完整或持久原子CAS。69/54af的限制仍完整适用。

generator的`stage(lineage=...)`仅为新版本viaU正例显式构造新输入，`state(cap=...)`
显式保留pending pair；`stage_request`只包装所给current/proposed，不做补全。
_negative中的旧null/partial/changed等仍作负例。没有自动3→2、推断lineage或用
目标返回修generator。原e6/061/612输入、源码与BLOCKED结论不回写成通过。

## 精度、identity、等待与完整值

逐支按公开8008/2bb/86规则复核现有Fraction数学：scale2..8；native int拒bool/
float；单腿abs<10^38，至多1000duties，joint P/U/N≤1000*(10^38−1)，derived
abs≤4000*10^38。minor→Fraction major再转回须denominator1；无binary64钱额
转换。P/U/N分别聚合，H=P+U且N不抵H；accrual=baseAccounting−P+N，risk=
baseRisk−H，available再减给定IM和order reserve，F不重复扣risk，ordinary为
C−F−H及零clamp。base必须EXCLUDED。未推导数量/mark/rate/cap或实际现金腿。

backing仅为给定prior clear且F≤max(C−ownP,0)的条件数据投影；WAIT保原cash/
P/U/N/H，eligible仅去own P/H，保留other H/N，F0允许负cash。缺quote标recheck，
不构成已付款、健康或授权。五个自身金融函数及三个financial branches的AST
与e6相同；相对612共28函数AST未变，只有_stage/_allowed_step/_state/evaluate_request
四项变化。此AST事实只证明子范围保留，完整调用链仍已逐支按当前输入语义复核。

独立构造公开9/7/7 payload，sorted/compact/ASCII JSON，duty/action prefix在SHA
之外、policy为bare digest。对公开合成字面量仅作stdlib SHA数据核对，三digest与
测试literal一致；未调用reference/target hash函数，不是测试PASS。slot按六字段
顺序输出array；同时按duty与slot去重。period以calendar+integer days/seconds
检查canonical UTC whole-second、>=1970及interval整除，未读钟或用timestamp float。
policy/action hash不认证审批或新预算，scale/policy/duty/claim不创造第二action。

`_wait_record/_wait_preview:370–425` 检查有限时间与checked deadline加法、policy
动态界、attempt/last lineage、highwater不回退；先投影highwater/attempt/last/sticky
review，真正改变才revision+1。normal/default同一no-op规则，MAX不变可返回，
任何改变拒绝。deadline等号不查询，interval等号在predeadline/belowcap才计数，
最后attempt先计数后review。未知结果无退款、deadline无延长、债务/hold无释放。
`wait_records:508–519` 拒绝给定集合内重复action，即便policy或scale改变；不选
较大policy，不证明全局/持久shared budget或实际dispatch。

十个op均有显式完整value字段，response固定7键/schema3，失败value留null并带
精确diagnostic。wait_records返回自身真实计算的canonical IDs全部有序列表，
不是count-only；未来目标bridge必须保目标实际tuple/order，不能按参考重排或代算。
本审查没有actual full-field comparison PASS，也不把oracle算式供作bridge实现。

## Transport、异常与覆盖边界

独立迭代walker`99–150`：root depth0，container/scalar每路径appearance计一次，
dict key/value分别parent+1；exit frames不计节点，waiting只计未访问节点，
visited+waiting+children作必需下界。active ID为path-local，拒ancestor cycle，
普通alias退出后重计。depth32、nodes250000、128 decimal digits（负号不算）
inclusive；raw UTF8与decoded compactASCII分别≤2MiB。loader显式UTF8，拒duplicate
key/BOM/invalidUTF8/NaN/Infinity/1e999，finite float仅可过transport，typed钱额/
time/schema拒绝其且不强转。原生evaluate无rawbytes，raw上界归loader。

transport在business catch外；envelope exact keys/int3/case_id/op/input先验后才
有response。坏envelope抛ReferenceWireReject而不造ID。evaluate仅捕自有显式
ReferenceUnsupported/ReferenceReject族，bare RuntimeError/ValueError/TypeError
逃出；测试301–307增加三种fault定义但全未运行。不签任意monkeypatch未知子类
或外部caller再分类；loader的转换错误仍在业务response之外。未来caller不得把
未知技术错误或valid-case的意外wire失败当“双方拒绝一致”洗绿。

33方法＝30个adapted forward定义+3 lineage组。源码分区为八类各64valid/
64negative，合计512+512；valid identity32duty/16policy/16action，10op均有分支。
新增lineage定义比较整个active/history/revision及输入不变，覆盖direct/viaU到三
final和missing/partial/changed/foreign/noU/history mismatch/cap breach。完整value/
IDs/transport与normal/MAX/deadline/interval等定义保留；test的局部schema checker
只支持固定wire用到的子集，不是一般JSON Schema证明。

这些都是定义覆盖。实际generated requests=0、status checked=0、test methods=0、
差分=0；没有1024样本通过、encoded maxima或资源峰值。manual仍为27行matrix、
17decompose+11payment+2special的partial slices，非原27整例PASS。dict-key节点
等号、alias展开budget等组合完整执行与一般codec等价仍未验收。多个1024循环及
大节点/duty fixtures意味着33方法不等于33请求，首次有限caller/source/budget须另审。

## 实际活动与保留门槛

本轮只Git/blob/bytes/JSON/AST及公开literal SHA数据检查：0 reference/generator/
target/validator import、call、bytecompile、casegen、test、SQL、proc/PID lookup或
signal、actor/service、network或CI。未读production算法或运行答案，保护进程
未lookup/signal；旧H1/AuthDB拒绝保持NOT_RUN，无重试或bypass，旧raw不改写。
parser/encoder部分先分配再检查，这些验证上限不是RSS/CPU/native-allocation硬配额；
完整codec/Unicode组合等价与恶意并发Python对象语义不由本CODE承诺。

本交付仅本报告+JSON两件SAFE资料；作者F/clean已只读核对。只在新review worktree
精确物化声明11blob，不改source/oldhistory/作者文件、mainindex，不用read-tree或sparse
reapply，不push。回滚只revert本审查，保留旧源码、规则、计划、raw和确认经济记录。
下一步仍须root另审immutable目标/参考/bridge/caller组合及首次资源scope。所有
activation_permission=false，reference selfcheck/target差分/normal CI保持NOT_RUN。
D2无条件BLOCKED；实际ACK/outbox/APPLIED、持久全入口fence、whole-period atomicity、
恢复、capacity/HA、真实资金与production均未批准。本报告不给任何执行GO或金融批准。
