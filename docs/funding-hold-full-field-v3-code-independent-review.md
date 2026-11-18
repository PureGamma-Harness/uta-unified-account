# Funding V3 完整响应驱动：独立有限 CODE 审查

固定 source `cd583c1e816ec9b9f65c237b2da457dea1d2638b`，结论 **CLOSED_LIMITED_DRIVER_CODE_NOT_RUN**。在本次 routing、完整响应比较、stream 收尾和失败上下文范围内，没有发现 CODE 阻断项。五个测试定义全部 NOT_RUN；这不授予运行 GO，不关闭 reference、target 或 D2。机器记录见 [review-cd583c1e.json](../evidence/reviews/funding-hold-full-field-v3-code-independent/review-cd583c1e.json)。

本审只读 driver、说明、当前与历史 candidate 元数据、公开 wire/API，以及冻结 generator 的 wrapper 元数据 AST。没有读取 target 金融 core 或 adapter 算法，没有按参考金融算法或 expected money 帮 root 写 bridge。driver 为 14215B、SHA256 `b6c82ad93093c4c67d55ef3945924b779a36cf86b45e6fc5fc28176199f43dd9`；doc 为 2805B、SHA256 `d442fa0652344dd82c83391a2099caad7988623eef7ce4478623ef687f71a906`，与 driver-context-candidate 的 pins 相同。旧 9da76b4d candidate 元数据仍逐 byte 保留，旧四定义/12259B pins 没有被当作当前五定义的 pins。

## Wrapper 合同核对

冻结 generator 的 wrapper exact keys 是 seed、family、partition、expected_status、request、hash_wire、activation_permission，request 位于 item[request]。hash_wire 确实声明为 CODE_CONTRACT_IMPLEMENTED_NOT_RUN，与 driver 假设一致；activation_permission 为 false。partition 仅 valid/negative；expected_status 仅 OK/REJECT/UNSUPPORTED，valid 声明 OK，negative 逐 case 声明具体 REJECT 或 UNSUPPORTED，没有合并状态或 allowed-set。case ID 的生成声明为 D1V3-SEED- 加四位补零 seed。上述仅由既有公开接口与 AST 元数据核对，没有运行 generator 或改变 C/F。

## 比较与收尾

每个完整 request 先变为 canonical ASCII JSON，再分别进入两侧自己的 loader 和 evaluator；两侧 decoded 对象互不复用。loader 前后序列化必须保持原始完整 request，evaluate 后输入必须与各自 evaluate 前相同。输出要求七个 exact envelope 字段、native schema3、case correlation、合法 status、对应 diagnostic、固定 false flag/tag；native 输出树不接受 float、subclass 或 cycle。

比较对象是完整 response 的 canonical bytes，不是金额、status 或 count 子集。对象 key 可排序以消除表示顺序，array 顺序保持；false 与 0 的 JSON 不同，extra/omitted value 字段也改变完整 bytes。first-difference 仅为已经失败的完整比较提供位置和 native 类型信息。driver 没有金融公式、预期金额常数或 DTO builder。

每个 actual status 还必须分别等于 generator 的具体声明；valid/negative 与声明 OK 的对应先检查，所以两侧一律拒绝不会通过 valid case。实际两侧 status counters 从各自已验证 response 取值，成功摘要独立报告它们，没有用声明数替换。

stream 必须恰有 1024 个有序 native int seed、1024 个唯一 schema3 case ID、十个 op 和 512/512 输入 partition。每次 next 的异常含 seed；提前 exhaustion 是技术失败；第 1025 项或末尾未知异常在成功摘要之前停止。完成计数只在该 case 全部检查后增加，完整摘要位于整个 stream exhaustion 及末尾断言之后。hash 用八字节长度前缀分帧，避免拼接歧义。

未知 loader/evaluator/serialization 异常成为 DifferentialTechnicalFailure 并保留 cause，不能伪装成匹配的业务 REJECT。完整 response bytes 不同的分支输出 seed、case/op/family、input/两侧 response SHA、有限差异位置及实际部分 counters。其它技术/合同失败提供 seed 和可得的有限 case-ID prefix/hash 上下文；它们并非每条路径都输出三项 stream hash，也不会输出成功摘要。实际 traceback/RAW、caller 退出与 EOF 证据仍须另行保留。

## 本结论的边界

cd583 的 Git tree 尚无三个 reference export Python 文件，说明已经明确这点。因此该 driver candidate 本身尚不是可运行的完整 source closure。后续必须集成固定 reference C/F、取得另组 reference CODE 结论、冻结 combined source 和 manifest，再由 root 分别审 exact caller、module provenance、资源和 capture 后授权第一次有限执行。

driver 独立检查的是 response envelope/native tree，并相对独立 reference 比较所有字段；它没有另写各 op value 的完整 JSON Schema validator，也不能证明金融语义。reference 自检和 target marshaller/core 的正确性属于各自范围。本驱动检查唯一 case ID 和 schema3，D1V3-SEED 字面前缀来自固定 generator 声明，没有单独 prefix 断言。families 实际计数会报告，细分 identity/family 覆盖由固定 reference definitions 的断言负责。

五个定义包括完整 stream、native type/array/extra-field 控制、未知异常、reject-all 及缺失首项控制，均未运行。本轮只做 Git bytes/SHA、AST parse 和 JSON 数据检查；没有 import、compile、generate、test、validator、SQL、actor、thread、proc/PID、网络或 CI。没有性能、容量、HA、真实 ACK/outbox、持久 CAS、资金或生产结论，D2 始终 BLOCKED。

行政记录：新建 no-checkout review worktree 的 index 初始为空，sparse 配置本身未物化；随后仅在该新 owned worktree 用不可变 tree 的 mode/OID/path 元数据初始化其 index，省略路径标记 skip-worktree，四个审查输入以 exclusive-create 物化。未用 read-tree/reset/clean/restore/reapply，未改 author source、main index 或 reference C/F。交付只新增此说明与 JSON 两份 SAFE；回滚只移除这两份，不改历史候选或旧结果。
