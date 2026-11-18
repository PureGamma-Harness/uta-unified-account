# Publication pending 形式模型独立 CODE 审查

审查固定源码 `2ff960eb7ec5b5ad19e366448237a010254c7f47`，parent `d1fd381bde923dc4010977058b76e34d6162e9a9`。**CODE_READY_FOR_SEPARATELY_APPROVED_BOUNDED_PURE_DATA_PLAN**：未发现阻止有限纯数据首次运行的源码问题，但本报告不授予运行许可。模型11472 bytes、SHA-256 `8d6ead3a0f9c9d58c52d6659db3fac090bea9b9f9b5e57d6430eefef247f93fb`；三份源码/文档/manifest的Git blob、大小、SHA均匹配。

本次只读Git/源码、AST和JSON，**目标执行0**：没有调用explore/replay/run，没有目标import、compile、单测、SQL、proc/PID、worker或网络操作。模型与原候选/首次失败证据未修改。详细记录见 [code-review.json](../evidence/reviews/publication-pending-model-independent/code-review.json)。

## 不变量、覆盖与故障因果

初始market0与两片installed/observed0相符，命令PENDING/attempt0/reservation0没有自相矛盾。完整发布→gap→activation→接纳、发布中halt、activation中halt、paused restart以及fatal退出都有人工可读的有限路径；这些路径不是实际搜索输出。七个baseline coverage都有非空手工见证。

逐一阅读八个mutation，可构造只由该变体触发指定tag的坏终点：fatal仍留pending、旧publication复活pause、旧activation越过operator halt、单片receipt提前market可见、paused poll计attempt、同CID再占用、过期quote被activation接受、restart丢pause。run要求指定tag出现，若首先发现的只是无关错误会assert失败；没有靠“任意报错”把负例判绿。只有exception_without_freeze关联6057对3a源码的历史静态CODE finding，其他七个是明确假想控制，不是运行时漏洞。

market epoch与operator intent revision分别保存。人工路径在market未变时把operator revision0推进1，旧publication保留halt/清pause，旧activation因captured/current不等而不能开闸。没有用market map相同替代operator intent相同。

## replay、限界与错误可见性

replay从真实初始State开始，逐步重新调用模型edges产生候选，要求action与完整JSON状态同时匹配且唯一，检查每个非终点无不变量错误，最后重新计算指定不变量；它不把trace中的state直接恢复为权威状态，也不信任输出的passed。JSON roundtrip会把tuple变list，plain统一转换，比较仍有定义。

baseline只有队列耗尽、无错误、所有coverage为正才成功。每variant最多25000个新状态，超过就抛明确INCOMPLETE，不返回最终passed。负例找到第一个反例时complete=false是预期的“反例已找到”，不是声称负例已穷尽，也不等于状态限界溢出。run还要求该反例JSON往返后replay成功。

两个非阻断解释限制必须保留：coverage是**状态计数**，例如recovered_pause也可能来自“先restart后开始publication”；admitted也包含初始generation0接纳。正计数本身不证明每个崩溃位置或特定接纳顺序被覆盖。真实BFS若穷尽仍检查所有可达边，但不能把计数改称完整事件覆盖。

## 纯数据预算建议

AST仅导入collections、dataclasses、json；脚本没有UTA、SQL、文件、clock、process/thread/network API，也无eval/exec/compile/dynamic import。解释器/stdlib的正常加载仍是受信环境假设，不是沙箱或零底层文件读取保证。

建议由root另立首次计划：固定解释器/源SHA，-I/-S/-B，单预选CPU、单并发、wall≤60s、内存≤512MiB、stdout≤1MiB、stderr≤64KiB、≤8个capture文件且总量≤8MiB、一个新独立数据namespace、仅一次尝试。九variant各25000状态上限，总发现状态不超过225000；静态审查不能保证在所提资源预算内完成。预算不是本报告批准运行；确切argv、外部退出见证与限界留痕须先由新计划固定。

未来验收需同时有外部exit0、完整EOF/JSON、source pins不变、baseline complete且无violation/coverage皆正、八个指定tag及replayed=true。非零、超限、超时、输出不完整或结果未知保留首样本并记FAIL_OR_UNKNOWN，不自动重试，也不只看passed字段。stdout写失败/外部capture失败不能变成模型成功。

## 证明边界与回滚

该模型把最后准入与预占、fatal stop持久写、两片receipt、operator revision和restart读取视作原子可信事实；它不能证明这些假设在真实SQL/进程成立。stop-record写失败不在模型内，实际运行时若不能确认必须UNKNOWN。没有refinement、liveness/fairness、physical fsync/lease-age、多个账户FIFO/撤单还款、资金量/费用/撮合/部分成交、未知batch恢复、HA或生产证明。

本提交只加两份独立review；revert即可撤回，不改变模型、原静态finding或任何金融数据。模型仍NOT_RUN，后续由root决定是否批准新的有限纯数据首次计划。
