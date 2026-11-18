# Native readiness 准备：独立行为审查未通过

固定目标 `0fbf6797b6a2f0c3bd8ed5782c303b024b48da90`。**新合成行为批次8项：1 PASS / 7 FAIL / 0 ERROR，exit1。** 本批只运行选出的 exporter/process_start AST，依赖全部为内存路径、内存writer和不启动进程的spy；没有运行目标模块、preflight、native case、UTA、SQL、child、pidfd、/proc、信号、网络或真实文件适配器。实际 native 与 preflight 继续 NO_GO。

## 已核实的正向范围

manifest 69项逐文件SHA符合固定Git：61个UTA Python文件、4个test/helper、4个native harness，共1,473,302B。它不是完整发行包或每个标准库/运行时文件的证明；实际child import origins尚未执行验证。原UTA tree与8d6e785相同；malformed case、initialize和market三函数AST未变，候选helper/采样器与4179首证据相同。原纯7项的6个证据文件逐字节保留，affinity[0]没有重解释为CPU编号1。

case只选择原malformed方法一次，要求三原负控按序到达并通过；初始activate失败不能算已覆盖这些负控。TTL2s、lease1s、publish8s、activation8s保持；原explicit snapshot的身份/时刻/内容不被替换。diagnostics wrapper在私有日志记录完整原对象后返回同一对象，没有伪造owner或financial ready。helper的首before-quote unknown仍立即失败，不重采；后续原采样/各负控的独立diagnostics均需逐次保留。第二个same-version case没有被执行或解释为同因。

## 三组阻塞与实际反例

| ID | 问题 | 首行为结果 |
| --- | --- | --- |
| RN-01 | journal_complete不核完整session、连续sequence、一一call及case-result/controls证据一致 | 5个畸变case都错误返回true，5 FAIL |
| RN-02 | process_start在original_start之后才核live count/name | 第三live worker的inert start spy实际调用1次，应为0，1 FAIL |
| RN-03 | safe_report丢弃top-level observation_error | 应保留安全type/sqlite code，实际缺失，1 FAIL |

RN-01的五个独立畸变分别为：删除整对diagnostic before/after并重编号，但case-result仍声称5 calls；只保留一个完整对的前缀而保留独立case PASS；重复一个sequence并产生gap；删除case_end；删除一条原subtest证据并重编号而case-result仍声称三项PASS。当前exporter只检查每行换行/JSON与call集合相等，所以均错误声称journal_complete。完整24-record正控通过，保留5条diagnostics且不把首owner witness提升为financial readiness。

修复必须区分“实际session记录结构完整”和“case PASS的三个controls完整通过”。诚实的早期断言FAIL可以只有0个controls；若case_begin/end、全部实际calls及case-result一致，其FAIL应被完整保留，不能为了补齐controls重跑，也不能一概改成UNKNOWN。本批五个缺证反例全部带有声称PASS/5 calls/3 controls的矛盾独立结果。

RN-02的max2约束需要在start前合法name/名额检查并保留sticky denial；如允许并发start，还应预留名额，防止并发检查后各自启动。start后的计数仍有价值，但不能替代禁止第三次实际spawn的前置条件。本批只调用不启动任何进程的spy，不是实际第三worker实验。

RN-03只要求top-level error的固定安全字段；合成message字段不得公开。现私有raw保存完整对象，不等于公开诊断已保留可复核的unknown元数据。worker层已有相应字段可作为一致设计参照。

## 首次证据与审查边界

预执行源码 `7809b59cb02a91ff9bd19c6dbee41321500a38a2`，独立脚本SHA `d9d51a6682c678fd433008582f93cf9f4085d930afb0adf6c29123877b55d683`。唯一CPU编号3/10s批次，最多24条JSONL、每输入小于64KiB；实际外层107,920,242ns、unittest0.012s。stdout为空；完整stderr7,573B，SHA `5b5148f0fc6591f5ace15f2c0302bd666c793536408099f54b4532f6c6e3cb83`，见 [首次stderr](../evidence/reviews/readiness-native-case-independent/first.stderr.txt)。全部first文件O_EXCL创建，未重跑原7、其他12或本8。

来源与原测试绑定见 [静态记录](../evidence/reviews/readiness-native-case-independent/source-contract-bindings.json)。外层45s、protected PID、pidfd与实际信号闭包由另一独立审查负责；本审查不替其签字。instrumentation的fsync本身会影响真实时序，任何后续local结果也不能替代原两项CI FAIL或证明共同原因。

本OWN只新增独立源码、计划、首输出、静态绑定和文档，无目标修改、风险配置/schema/数据迁移或生产部署。回滚移除此OWN新文件并保留全部首FAIL和旧原件。修复须用新固定源码与新具体预算验收；passing纯fixture或metadata都不能自动授予native GO、financial readiness或真实资金启用。
