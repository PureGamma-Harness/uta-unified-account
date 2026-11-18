# 产品矩阵独立交叉审阅

结论：**SAFE，仅限修订后的 docs/data 矩阵交付**。审阅 tip 为 `977b4e9b541bac5aae42906b2541e77738ea70fc`，其冻结源码仍为 `2b1b2a6d493c3258ce0446b45959f76318cb17d6`。P1/P2/P3 生产结论继续 **NO_GO**；本报告不验证运行行为、性能、金融规则校准或生产启用。

原审件 `4fc54d933fea4af9ccc228fc80ca478cdf81deaa` 有两处需改的静态表述，已反馈作者，由作者独立修复后重审；本组没有修改矩阵作者源或当前 runtime 候选。

| 历史问题 | 作者修复 | 重审结果 |
| --- | --- | --- |
| P1-08/P1-09 的入口与符号写为不存在的 `LocalMatcher`，冻结源码实际类名为 `Matcher` | `269e55208bd49d2ddc284b557f98695cf7784512` 同步修订 Markdown 与 JSON | 新矩阵无旧名，`uta/matching.py:Matcher.match_once` 与 CLI 实际装配吻合 |
| P1-32 将无 perp 仓位且债务困境一概表述为 BLOCKED，遗漏 `equity<0` 先进入 BANKRUPT 的分支 | `977b4e9b541bac5aae42906b2541e77738ea70fc` 区分负权益 BANKRUPT 与非负权益/债务阈值/滞回的 BLOCKED；并补 P1-19 USD8/BTC8 精度引用 | 与 `uta/service.py:1138–1155`、`uta/credit_native_v2.py:203–217,1157–1159` 静态分支一致 |

结构验证只用 stdlib 解析公开 JSON、正则比对 Markdown 行 ID、计算 source bytes/hash，以及 Git object 只读访问；没有导入、编译或运行 UTA，没有测试收集/执行、SQL、worker、负载、网络或 PID 操作。没有读取 archive 或私有 raw；H1/Auth/DB8 仍为被拒绝的 NOT_RUN。

结构结果：47 个唯一矩阵行与 Markdown 的47个行 ID 相等；73个显式 source files 合计1,551,658 bytes，全部 SHA-256、Git blob与冻结 `2b1b2a6d` 相等；每行 evidence/test 引用与 manifest相等；82个 test-reference entries 全为 NOT_RUN；47行生产决策全为NO_GO。已有 combined manifest中的67 runtime files /1,494,225B /66 Python只作源码清单计数，没有运行或部署观察。所有结构校验 errors=[]。机器记录见 [review.json](../evidence/audits/product-mode-capacity-independent/review.json)。

| 重点边界 | 静态复核依据与结论 |
| --- | --- |
| v1 显式借贷 | `gateway.py:460–471,514–522` 确有 pool、asset-limit、account loans入口；`credit.py:275–374` 有同事务额度/池/风险检查。矩阵P1-17只标STATIC_PATH_AVAILABLE，部署值UNDETERMINED，不把quote当借贷权限 |
| 普通 managed v2 新借贷 | `durable_gateway.py:290–316` 只有 orders/cancel/repay已知account命令，其余指定合法account操作进入501；`durable_commands.py` 无普通BORROW kind。P1-18保留明确拒绝且限定接口，没有否认内部例外 |
| internal format2 BTC 例外 | `credit.py:301–314` 要求实际format2与native operation context；`credit_fifo_v2.py:134–225` 的内部显式synthetic source/FIFO；`credit_native_v2.py` 要USD8/BTC8、BTC-only、descriptor production_approved严格false。`service.py:1281–1290` 返回trading readiness=false。P1-19没有提升为普通gateway借贷或生产权限 |
| 还款 | v1 repayments、v2 REPAY 与内部format2 REPAY分开；metadata ACK不表示债务减少。`credit.py:396–441` 同币现金、interest first、拒绝overpayment且无需当前行情/解除halt。P1-23边界正确 |
| Isolated / PM | `products.py:190–209`、`portfolio.py:259–264` 拒绝非Cross；ScenarioReference.pm_activatable为init=False固定false。M-01/P3-03只报告指定入口拒绝，没有因enum或研究计算器存在而启用 |
| 私有WS | `private_stream_codec.py:1–6` 明确unused by every service/listener；已读gateway/CLI/managed入口没有装配该codec。P1-38区分REST分页与WS未连接，部署listeners保留UNDETERMINED |
| 新 funding hold | `funding_hold_pure.py` 为USD supplied-data pure接口，activation_permission默认false且init=False；没有financial admission/payment接线，APPLIED新hold不因旧FundingObligations的APPLIED而获准。P1-27保留NOT_RUN、无真实hold/ACK/outbox/owner/auth integration |
| 明确拒绝与未知调用 | 对unsupported account操作/strict fields/非Cross模式的拒绝均限定到所列HTTP或catalog接口；多处gap保留任意未审内部调用UNDETERMINED，不把“无公开入口”外推成所有内部代码拒绝 |
| 数值、成交与容量 | 金额精度、累计费ceil/PnL floor、本地两侧真实撮合与模拟/研究分开；每行无生产PASS，G3/G4继续要求>=1800秒真实持久唯一成功，不能用queue ACK、拒绝、拆腿或旧CI替代 |

Source hash完整性只是引用可定位性；本次未证明测试断言正确、金融金额正确或运行路径必然安全。未观察实际feature flags、资金规则、外部交易所映射、部署环境、回放或四侧数据库结果，继续保留矩阵的UNDETERMINED/NOT_RUN/NO_GO。

本报告与机器记录均为新增docs/data；可对本报告提交使用 `git revert <review_commit>` 撤回。它不授权合并runtime、部署、启用产品、执行测试/负载、重启旧进程或重跑被拒绝实验。
