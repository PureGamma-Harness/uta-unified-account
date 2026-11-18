# Market control CAS v2 集成树独立 CODE 审查

**CODE_NO_BLOCKER_FOR_FIRST_NORMAL_CI_ONLY**。可为固定集成树
`72dd3a17d7a8e363d95854ee8c4f361e0a24d901` 触发首次常规 CI。此结论不是功能验收、
custom22 capture 的执行许可或生产批准。本审查未导入、编译或运行目标，没有测试、
SQL、proc、worker、CI 或网络执行；组件 e510 的静态闭合也不等于本树运行通过。

基线为公开 PR57 源 `ef7508bebd35cac71d9db8fdda896806ce4ade64`。新树恰好改变
3 个 runtime 文件和 2 个测试文件，均逐字节来自已审组件
`e1c38cfed7838951303921ed98b449025cb334f9`；其余增加仅集成说明及 manifest。
7fb80af 到 72dd 仅修正文档计数。完整 66 runtime 文件的 Git blob、物理文件、大小、
SHA 和声明 origin 均匹配，合计 1470877 bytes：65 Python 加 1 HTML。其余 63 个
runtime 文件精确保持公开基线，已检查的 session 私有祖先 denylist 命中为 0。
详见 [机器记录](../evidence/reviews/market-control-cas-v2-integration/independent-code-review.json)。

V3 源清单仍明确列出 65 个 Python 文件，与新树路径集合相同，测试本身保持基线
原字节；本 overlay 没有新增 runtime 模块，因此不需要改 V2/V3 或新增清单版本。
这与另行开发的 D1 binding 新模块范围无关。

静态兼容性核对未发现首次 CI 阻断项：

- QueueStore 原有参数/默认保持，新增 `allow_submit=True`。显式市场 pause 时只筛掉
  SUBMIT 候选，FIFO 子查询仍检查所有更早的 PENDING 前驱；被筛掉的行尚未进入执行、
  尝试次数或回执更新。同账户 cancel/repay 在其后仍被阻塞，文档明确保留该限制。
- managed 两个首 EX 阶段在持久写及 enqueue 后重新读取整个控制 payload，生成不可变
  identity；两个后续 EX 阶段和 late fatal 回执路径都在全局状态修改前检查相同 identity。
  full payload 不同返回 409，不覆盖后继状态；timeout/UNKNOWN 不伪装为已 superseded。
- 激活/显式 halt/完整性失败保持原行情、来源、资金 registry、fencing 和最终校验；
  `_write_state` 在 active 或独立停止状态清除 pending。stop 写失败保留原错误与 UNKNOWN
  因果链，不宣称停止已提交。原 freshness、fee、precision 等参数没有放宽。
- ExchangeService 的组件既有 callable 签名保持；CreditService、existing-services、
  startup 和 batch 模块与组件同字节。公开基线新增的 admission summary/policy 仍由
  service/DecisionAudit 承担；CreditAuditV2 明确调用 valuation_policy，未混入新 admission
  字段。overlay 的构造器、queue 和交易调用仍匹配这些接口。
- 三个 funding 文件保持公开基线字节，overlay 未导入或启用它们；router 的 funding
  registry 检查仍是 credit-pool source claims，不能称为 pending funding encumbrance。

这是显式 experimental control protocol revision2。旧等待者不得按旧 oracle 继续更新，
客户遇 409 应查询原 CID 和当前控制状态后再决定显式新请求。旧 3a/deb 计划、冻结源
或测试结果不能借来验收本树。身份比较的 native/i64/depth16/work4096/1MiB 上限只约束
接受的 identity；它不是所有控制写的 pre-write quota、predecode 限制、溢出恢复、物理
I/O 或 kernel 目录配额证明。

新增两个测试文件定义 22 方法（5 state、17 SQL），尚未运行。首次完整 CI 的正确性、
安装包与新组件测试范围，以及 custom22 producer、有限首次执行与 RAW，分别需要实际
证据。fresh isolated synthetic namespace 边界不变；没有自动既有 authority 迁移、旧
writer 退休、artifact reseal 或新增金融能力。撮合/账本对账、故障/HA、持续万笔容量及
真实资金审批仍开放。回滚须按实际 ownership 停写并保留、查询和对账原业务回执，不能
用旧快照覆盖已确认历史。本次仅新增两份 review，revert 不影响 runtime 或金融状态。
