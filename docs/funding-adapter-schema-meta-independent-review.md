# Funding adapter schema-meta：独立有限 CODE 审查

固定 `f8ece4c2257f2340e4b59fc0a113ac2b96ff9115`，parent
`afdd92104ccd2ab0f39a1b94ddcf7797211e38fe`。结论为
**CODE_CLOSED_FOR_OUTPUT_SCHEMA_META_DELTA / NOT_RUN**：FTA-V3-B4 的
value-dependent schema 支持检查在本不可变源上闭合；原 B1/B2/B3 的有限
静态闭合保持。没有运行 validator、测试或目标，不签一般 JSON Schema、
金融结果、codec 等价、完整差分、D2 或生产验收。

机器记录见 [review-f8ece4c2.json](../evidence/reviews/funding-adapter-schema-meta-independent/review-f8ece4c2.json)。

## 固定来源与范围

完整阅读 475 行实际 mapper、203 行测试、原 `1b456fd1` 和 `afdd9210`
两份正式报告及公开 061 wire。候选三项内容 pin 的物理/Git SHA、length
一致，四个 delta 文件均固定到 f8；wire 原件仍为31,492B / SHA
`d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be`，
与061的公开对象逐字节一致。相对 parent 没有 UTA runtime 改动。

静态 AST 确认全部11个原 nonvalidator 函数，以及其他模块级声明和 class
均与4173相同，尤其 `_call/evaluate/_checked_intermediate/_encode` 的异常、
完整输出和中间返回 guard 没变。旧 value validator 只改函数名及递归调用名
后，与 `_match_output` AST 精确相同。原16个测试方法 AST 不变，新增2个，
共18个方法全部 NOT_RUN。

本轮只做源/Git/JSON/AST 数据检查，没有 import、字节编译、调用 adapter/
validator/target/reference、生成案例或运行测试，也没有 SQL、读钟、proc/PID、
actor、网络或 CI。没有读取生产核心或独立参考的金融算法求答案；既往其他
审查任务的知识不作为本包装器金融正确性的证明。

## B4 的新控制流

`_validate_output:296–298` 先完整调用 `_check_output_schema`，成功返回后才
调用 `_match_output`。meta 函数没有 value 参数，不引用 `_OutputMismatch`，
也没有进入 matcher 的调用；它的所有不支持情况都是技术失败。

meta 对每个选定输出 root 的完整可达 closure 检查：

- `$ref` 只能有此单键，原生字符串前缀、存在的 definition 及 active ref-path
  检查在递归前完成，循环引用技术拒绝；退出时移除 active，允许普通 DAG 复用。
- `oneOf` 必须为1..4个原生 list alternatives 且无其他键。每一个分支都递归，
  不能因为 null 或其他分支能匹配 value 而跳过未知 branch。
- object 的 properties/required 是原生 dict/list，所有名称为原生 str，required
  不重复、两者集合相等、additionalProperties 必须是确切 false；每个 property
  都先递归。array 必须有 items，并无条件递归 items，即便 value 不为 array
  或为空也不跳过其 schema。
- type 仅 object/array/integer/string/boolean/null；各 type-family 的 keyword
  集合明确，其余未知或跨 family feature 技术拒绝。const/enum 只准声明的
  native primitive 子集，enum 为1..32的 list，字符串冒充 enum 不接受。
- bounds 为原生 int，bool 不充当0/1；长度界非负，所检查的 min/max 对一致。
  pattern 必须为有界 str，regex syntax 错误另归技术错误。depth32/work8192
  在递归前检查，未知 schema 不进入 value matcher。

因此旧反例 number type、type list、未选 object 内 unknown property、未选
array item、required="x"、空 nested oneOf、maxItems=true 与 enum="x"
均在 schema 阶段失败；不能再被外层 oneOf 当作普通 value mismatch 丢掉。
相反，一个合法但无匹配值/匹配多个 alternatives 的 schema 可以产生
`_OutputMismatch`，此时才由 value oneOf 作匹配选择。这是有意的分类。

上述为代码路径检查，不是已运行负例。新两个方法包含相应 inert 条件，但未执行。
未在本轮生成额外 test 或调用被审 validator 来证明它自己正确。

## 保留的完整 mapper 边界

成功 target 返回在 business try-else 外编码并验证选定 op 的完整 value。
policy 携实际 DTO、wait_records 携实际 validator tuple，其所有 IDs/order
不重算、不排序修正、不替成 count。natural_slot 先查原生六字符串 tuple。
decompose 在调用下游前验证真实 Totals 类型及完整 wire；错误中间返回不会
由后续 target input guard 洗成业务 REJECT。下游在两个输入已接受后抛出的
HoldError 仍为保留 cause 的 AdapterContractError。

只允许确切已知 InputReject/HoldError/HoldUnsupported 归业务响应；subclass/
未知构造器错误、编码/输出/schema 错误仍逃出为技术失败。编码时逃出的
HoldError 即便类型名字相同，也没有被 adapter 归为业务 response；未来 caller
不能在外面再次按异常类型把它洗成业务匹配。这个外部执行器仍须另审。

这些 guard 的 AST 保持，原报告与原失败/NOT_RUN 状态没有被重写。完整字段
和 schema 正确不等于金融数字、history/lineage 或全 op 行为已经与参考一致。

## 限定与后续

独立 JSON 图统计，十个**选定输出** closure 的最大展开节点99、depth9，
低于8192/32；使用六种支持类型，没有实际 number/未知 feature。该统计不传
value，也不调用 mapper validator。通用 request.input 本来是不封闭的 transport
对象，不属于这个 closed-output 检查；未引用的其他 schema root 也不是一次
调用自动验证的对象。

本结论假设 hash 固定的 native JSON schema graph 在一次检查/匹配间不被外部
并发篡改。它不是任意可变 Python schema 对象、一般 JSON Schema 2020-12、
regex 全语义/性能或所有库 keyword 的支持证明。meta 在**匹配**之前，不等于
在 target 纯调用或原生值编码之前；编码先失败时本身已是技术失败，没有 OK
或被 oneOf 隐藏的 schema 通过。深度/work/文件上限也不是内核 RSS/CPU 硬配额。

18个方法均只是定义，codec、全字段差分、数值/状态语义、完整 reference、
实际 runtime/资源和 normal CI 均未验收；参考612的独立 lineage 阻断不因
此包装器 CODE 审查消失。所有 activation_permission 仍 false，D2、资金/
服务接入、真实 ACK/outbox、原子结算、恢复和真实资金生产仍 NO_GO。

本交付只新增两份 SAFE 审查资料，未改 f8/4173/1b456/afdd/wire/作者工作区、
生产或参考源码、旧 raw/计划，未 push。回滚仅 revert 审查。之后须 root 另审
不可变目标/参考/执行器组合及 exact 首次资源 scope；本 CODE 不授执行 GO。
