# 独立 funding D1 v3：最终状态 lineage 的 CODE_ONLY 参考

新增三个自含测试侧 Python 源、独立 manual 数据副本及冻结清单。所有参考、生成器、测试、目标执行均为 **NOT_RUN**，D2、生产与真实资金仍 BLOCKED。旧 e6、061、612 的全部原件和旧 BLOCKED 结论保持原字节，不把旧 null 输入修成新正例，也不改写历史结果。

本版唯一规则输入为公开 8008/895、2bb8095f 及独立规则审 86b3c2ac，再加前向最终 lineage 规则 69a3e32e 和独立有限审查 54af0876。旧 612 源的 `_stage` 强制最终 E/C 为 null，被 04dfc2d2 标记 BLOCKED；本版从自身旧 Fraction 源独立推进，不读取新的 production financial core、target adapter、DTO 验证器、helper、builder 或运行答案。

## 新规则及提供历史的限制

直接 REGISTERED_UNASSESSED→FINAL_PAYABLE/FINAL_RECEIVABLE/FINAL_ZERO，最终 exposure_ref 与 cap_ref 均为 null；经 EXPOSURE_RATE_PENDING→任一最终类型，最终 E/C 必须与不可变历史 U 的完整 ContentRef 逐字段相等。两条路径均另外要求 FINAL_CUT final_ref。缺失一项或两项、改变、foreign duty/scope、无 U 却附 lineage、当前 refs 与提供历史不一致，均拒绝。完整 expected Stage 与 revision 的 CAS、给定 cap 上限、最终状态不可修改与 history 长度限制继续适用。

保留 refs 只检查当前提供历史的内部一致性，不认证内容、审批、全局完整历史或真正 provenance。一次仅有一个 active stage 贡献金额，历史 U 和 refs 不额外贡献 active U。给定 U600→P246 时 P246/U0/H246；转 N246 时 N246/H0；转 zero 时 P/U/N/H 全零。这是公开规则的给定数字切片，未派生任何数量、mark、rate、cap 或最终现金腿。

## 公开接口与完整交付

[public-export.json](../evidence/designs/funding-hold-exact-reference-v3/public-export.json) 是精确 11 文件清单。新文件相互自含，manual 数字与 e6 的固定 JSON blob 逐 byte 相同，测试仅使用新 v3 数据路径，不依赖旧参考程序。源码提交 C 冻结十个非 manifest 文件；后继 manifest-only 提交 F 固定这十个 C blob 的 bytes/SHA，F 自身以不可变 Git commit 固定，不写循环自 hash。

| 模块 | 对外入口 |
| --- | --- |
| reference_funding_hold_d1_v3 | evaluate_request(request)、load_request(raw) |
| funding_hold_d1_reference_cases_v3 | case_for_seed(seed)、iter_cases() |

三个模块放在同一 tests 导入目录。load_request 接受 native str/bytes 并返回受限的解码树；evaluate_request 接受封闭 v3 envelope，返回完整 response。无有效 envelope 或 malformed transport 必须抛 ReferenceWireReject；内部未知异常逃出，不能泛抓成业务拒绝。seed 为 native int 0..1023，bool 拒绝；case 元数据包含 seed/family/partition/expected_status/request/hash_wire/activation_permission。iter_cases 按 seed 升序给出同一封闭域，生成器不导入 oracle 或 target。

冻结 [wire-contract.json](../evidence/designs/funding-hold-exact-reference-v3/wire-contract.json) 为 d3586666 的 33268B，SHA256 `6dd60f660a9a16c836b3572c7183d5a2085f2ff3ffae82fa66c7d4bdbf2b3bcd`。协议 PFH-D1-INDEPENDENT-WIRE-v3，request/response schema 均为 3；不接受或自动重写 schema 2。十个 op、所有 DTO/input/value 字段、输出 flag、类型、顺序和错误分类均按 wire 完整比较，不能仅比 status/count/金额子集。hash_wire 为 CODE_CONTRACT_IMPLEMENTED_NOT_RUN，activation_permission 永为 false。

root-owned bridge 只需公开 wire、规则和上述入口接口；不得按 oracle 算法或期望程序实现目标逻辑。bridge 只能 exact DTO 构造、目标 API 调用和完整字段序列化，不能补 refs、自动修旧负例、重排序 target 返回的 action IDs 或自行推导金融公式。独立 bridge CODE、decoder 等价性和首次 caller 执行仍需另审。

061 的资源规则完整继承：root depth=0；container/scalar 每路径 occurrence 计一次，dict key 与 value 分别在 parent+1 计数，alias 重复计、ancestor cycle 拒绝；depth≤32、nodes≤250000、整数十进制位数≤128（不含负号）。raw UTF8 与 decoded compact ASCII 分别≤2 MiB；重复 key、BOM、非法 UTF8、NaN/Infinity 和 1e999 溢出均为 transport 拒绝。finite float 仅可经过 transport，exact typed money 不转换接受它。这些是验证限额，不是 native parser 的 allocation/RSS 硬限额。

## 已定义范围与实际检查

33 个测试方法为 30 个前向定义加 3 个 lineage 组。新 D1V3-SEED-0000..1023 仍为八类各 64 valid+64 negative，共 512+512；有效 identity 是 32 duty、16 policy、16 action，十个 op 都有定义分支，测试中还定义了显式覆盖断言。实际生成请求数、状态核对数、编码最大值、峰值资源和耗时均 NOT_RUN。

三组 lineage 覆盖 direct 与 via U 到 P/N/zero，比较整个 active/history/revision，检查输入不变；拒绝 missing/partial/changed/foreign pair、缺 FINAL_CUT、没有 U 却带 pair、提供历史被换到不一致，以及 cap breach。原完整 Stage/revision、final immutability 与等待边界负例保留。全部定义未执行。

manual 仍是 27 行原矩阵、17 decomposition、11 payment、2 special 切片，无一变成原始完整场景 PASS；M14 quote80、真实 ledger ACK/APPLIED、outbox、持久 CAS、整期原子性、恢复与全局唯一继续不支持。H=P+U、N 不抵 H、给定 base 的 once-only gross 分解、backing 支付投影及等待预算规则仍按原公开规则；没有新增金融入口。

本轮实际检查只做 Git/原始字节/AST/JSON 数据检查：三源可 AST parse、33 方法定义、imports 白名单、wire 固定 bytes/SHA、manual 与 e6 blob 相同、旧工件 Git blobs 保留、精确导出清单和新 C/F pins。没有导入、编译、调用参考/生成器/测试/目标，没有 SQL、actor、线程、proc/PID、网络或 CI。JSON/字节一致不能称为算法正确、decoder 等价或测试 PASS。

评审只针对不可变 C/F CODE；另组 CODE 关闭后，由 root 单独固定首次有限执行的 source/caller pins、资源限额与原始证据，不允许自动运行或重试。后续每个自检、差分、CI、D2、容量、HA 结论须独立陈述。回滚仅移除新 v3 源/元数据 delta，保留所有旧版本与确认经济记录，不迁移数据或部署金融能力。
