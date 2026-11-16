# Managed authority 的独立有界模型

协议参考版本为 `d5d2887626497671718edb5cf32c147b4fa3bb27`。本组只新增 `formal/explore_managed_authority.py`、`tests/test_managed_authority_model.py` 与本报告，不修改运行时。模型仅导入collections、dataclasses、json，不复用UTA实现、风险计算器或既有formal模型生成结论。

交付是**两张独立安全抽象图**，不是二者的组合证明，也不是生产代码的精化/等价证明。脚本输出 `composition_proven=false` 与 `production_approved=false`。不从有限状态数推出跨AZ、持续万笔、24小时稳定性或真实资金批准。

## 模型A：写者身份、孤儿恢复与行情屏障

边界为两个分片、每片最多两代合法owner、旧/新两个coordinator。合法进程出生身份用1/2代表；同一数字PID被不相关进程复用时出生身份为9。初始行情代次0在两片均已确认，只再发布一次代次1。最多准备一条新增风险命令、提交一次风险事务，因此没有枚举多个跨片金融写事务同时运行。

状态显式区分RUNNING、SIGSTOP、退出、PID复用，旧/新owner的有效租约，以及coordinator死亡与重新取得supervisor锁。旧coordinator死亡不会自动消除旧进程、旧租约或已持有的SH gate。新coordinator只能在对应旧租约到期、出生身份仍与持久登记相符后回收旧进程；回收释放未提交work与其SH。PID已复用时保留不相关进程，不能凭数字PID杀进程。新owner必须取得更大generation及自己的出生身份，不继承旧token。

全局状态为HALT、PUBLISHING、ACTIVE。发布开始要求EX可用，随后两片分别提交实际行情，再由coordinator收集各自持久回执。完成fanout后仍HALT，必须显式激活；ACTIVE要求实际两片版本、目标版本与全部回执一致。新增风险从准备至COMMIT保留SH，COMMIT再次检查owner身份、租约、全局状态及所用行情代次。

**检查的性质：**同片不能存在两个重叠的有效租约授予；失效/旧generation不能提交；孤儿恢复不能杀掉不同出生身份或尚有有效租约的owner；不完整fanout不能激活或批准新增风险；SH不能在准备事务提交前释放。

每个风险COMMIT保存其**提交前状态**的token/current-generation、出生身份、租约、全局状态和行情证据。不把合法历史提交拿来与后来owner比较后误报：测试明确先合法提交、再到期/接管，要求原历史事实仍有效。

这里验证的是授权窗口和提交前检查，SQLite同库物理写事务串行化本身是前提。单个prepared风险命令是本模型的边界，不能用它宣称证明了任意数量并行事务的物理互斥。

## 模型B：持久命令、结果丢失与部分清算

边界为一个账户、三个不可变command ID、三个对应的金融订单/潜在fill ID，最多两个worker generation，一个原子本地金融提交。初始合资格长仓为2个归一化单位；可映射为已真实开仓90合约，每单位45。初始只有1单位真实对手深度，允许再增加一次，合计最多2。没有估值、现金、费用、借贷或保险基金计算。

`durably_queued`提交意图后可以没有订单和预占；它不等于金融SUCCEEDED。按同账户FIFO执行命令时，reduce-only累计未成交量必须小于等于当前仓位；订单占用与不可变命令终态同COMMIT。超额度命令形成REJECTED，不产生金融副作用。

**成交不是inbox的一种APPLY_FILL操作。**本图另有实际匹配/结算转换，只有已经接纳、仍未成交的订单和真实可用深度才能触发；仓位、已成交量与唯一fill事实同提交。command ID和fill ID是不同的幂等域，不能因查询或重新投递原回执而再次占用或结算。

COMMIT与回执投递分开。worker退出只丢失未提交准备工作及尚未投递的响应，已排队、已接纳及已成交事实保留。新generation重新打开原ID，查询/补发回执不改变金融状态。测试沿显式路径先成交1单位、在两类回执均未投递时退出、重启查询，要求仍余1；没有新深度时不能继续成交；补足深度后仅再成交1单位，最后第三条新增reduce命令按额度拒绝。

**检查的性质：**金融预占与成功终态不可拆开；客户端终态不得早于COMMIT；原command与原fill不能产生第二次影响；任何确认成交不得超过实际深度、订单数量或剩余仓位；累计只减仓占用不得重复；未确认指令不能减少仓位；清算不得反向或扩大初始仓位。

模型只覆盖这个长仓与单账户配置，不证明反向产品、空仓全域、组合对冲腿拆除、任意部分数量、币种资金守恒、PM或真实撮合价格优先。货币现金流与四侧对应由实际独立测试补充，不能从本图凭空推出。

## 实际完整枚举结果

```sh
python formal/explore_managed_authority.py
python -m unittest discover -s tests -p test_managed_authority_model.py -v
```

| 安全图 | 完整可达状态 | 带动作转换 | 违反 |
| --- | ---: | ---: | --- |
| A：两片owner/PIDbirth/屏障 | 32,816 | 161,256 | 无 |
| B：持久命令/部分清算 | 1,524 | 5,534 | 无 |

Python3.12.14下实际运行CLI退出0，`passed=true`，输出106,091字节JSON（含全部反例），约1.426秒；独立单元测试 **10/10通过、0 failures/errors/skips，1.378秒**。单元测试逐条重放JSON反例、检查正向恢复路径与非空覆盖、确认资源上限失败不能伪装成通过，并静态限制模型只能导入所声明的三个标准库模块。以上不是全仓测试数。

完整表示BFS队列已清空，不是达到计时/数量上限就返回通过。不同动作即使端点相同也分别计为转换；相同状态只入队一次。单次探索的资源保护上限为500,000状态，达到该上限会显式抛错；测试用上限1验证不完整探索不会获得通过。未知模型或拼错mutation同样拒绝。

可达性计数避免“规则把真实场景排除后空泛通过”：模型A实际包含416个停止孤儿持有SH的状态、8,256个部分fanout仍关闭的状态、7,200个第二代有效风险提交状态；模型B实际包含352个余1且无剩余深度状态、632个确认成交但回执未送达状态、288个按真实成交归零状态。单元测试另逐步执行**两个SIGSTOP旧worker→coordinator死亡→两租约到期→按birth回收→两片新generation→完整发布/显式激活→新owner提交**，验证这些状态不只孤立存在。

## 故意破坏约束的负控制

每个变体单独运行，只放宽列出的约束。以下状态/转换数是找到第一个反例时的发现量，不是坏图的完整枚举。每条反例均包含逐步动作和状态；测试将其转为JSON再读回，沿真实变体转换逐步重放，核对此前状态安全、末状态违反指定性质，并要求至少一条边确实区别于安全模型。

| 变体 | 首反例步数 | 已发现状态/转换 | 实际检测 |
| --- | ---: | --- | --- |
| A steal_live_lease | 3 | 138 / 262 | 同片两代有效lease窗口重叠 |
| A check_current_lease_without_token_identity | 7 | 2,900 / 9,910 | 只查当前lease有效而误允旧generation提交 |
| A skip_commit_expiry | 4 | 597 / 1,651 | COMMIT时租约已过期 |
| A kill_reused_pid_without_birth | 6 | 1,207 / 3,723 | 杀到同数字PID的不相关出生身份 |
| A kill_orphan_before_lease_expiry | 3 | 136 / 261 | 提前终止有效lease owner |
| A activate_partial_fanout | 4 | 560 / 1,498 | 只有一片回执就ACTIVE |
| A risk_commit_using_only_local_market | 4 | 638 / 1,657 | PUBLISHING期间凭本片新行情提交风险 |
| A release_shared_before_commit | 3 | 283 / 681 | 准备中的风险命令提前释放SH |
| B terminal_success_before_commit | 3 | 34 / 56 | 金融终态未提交已向客户确认 |
| B financial_without_terminal | 3 | 31 / 53 | 预占已变化而终态仍PENDING |
| B repeat_original_command | 7 | 195 / 461 | 同command ID再次产生金融影响 |
| B repeat_confirmed_fill_after_restart | 9 | 397 / 1,088 | 原fill ID重启后重复结算 |
| B count_unmatched_liquidation_as_filled | 5 | 86 / 180 | 未确认指令提前减少仓位 |
| B reverse_liquidation_direction | 5 | 83 / 177 | 清算将长仓扩大 |
| B overfill_order_quantity | 5 | 83 / 177 | 确认数量超过订单数量 |
| B skip_reduce_only_reservation | 9 | 322 / 844 | 累计只减仓预留超过剩余仓位 |

脚本仅在两张安全图完整通过、16个坏变体都产生真实非空反例时退出0。测试不使用“发现任意错误就算通过”的宽断言，而逐项核对具体违反名称。

## 与真实PID/金融证据的对应

| 抽象性质 | 真实实现回归 | 不能互相替代的边界 |
| --- | --- | --- |
| 两片、单owner与第二代恢复 | `tests/test_durable_process.py` 的独立PID、强杀后新owner及部分发布恢复 | 模型不启动进程，不执行SQLite或真实flock |
| coordinator死亡及停止孤儿回收 | 同文件 `test_new_parent_uses_registered_birth_identity_to_recover_sigstopped_orphans` | `/proc`解析、boot/UID、pidfd与信号正确性是模型前提；真实组合故障需实际执行 |
| 过期/旧token不能写 | `tests/test_durable_reference.py` 的租约等号、旧writer、clock高水位和birth变化；`tests/test_durable_faults.py` 的真实进程竞争 | 模型只含到期事件，不建立纳秒时钟、持久SQL/UDFguard或旧binary拒写的等价证明 |
| 排队/终态/未知结果与唯一占用 | `tests/test_durable_commands.py`、`tests/test_durable_reference.py` 的独立现金书与真实COMMIT丢响应；`tests/test_durable_faults.py` | WAL/FULL、物理FULL/COMMIT失败与进程退出后的落盘结果必须实际验证 |
| 45部分成交、无深度与新PID继续 | `tests/test_managed_liquidation.py` 的两个显式审计模式真实链路 | 模型归一化为2单位，不算93.16USD、费用、实际对手成交或四侧对账 |

这些映射指明证据的角色，不冒称本次形式化任务重新运行了上述真实PID套件，也不把历史通过数当作新候选结果。CI接入、最终集成SHA和实际运行日志由集成负责人单独归档。

## 假设与未证明范围

- 本地提交原子且耐久，已提交意图/终态/fill在进程退出后仍在；没有证明硬件fsync、磁盘掉电或复制确认。
- lease到期事件代表可信单调时钟越过明确边界；没有证明时钟实现、时钟回退处理或RTO。
- 持久登记先于worker取得权限，birth/boot/authority与pidfd真实指向目标进程；没有证明OS primitive或数据库完整性guard本身。
- SH/EX的模型动作是原子的，金融提交是单个原子动作；没有证明Linux flock、SQLite锁实现、任意并发事务或死锁自由。
- 没有两个组件的组合/精化证明，不证明任意规模、活性、公平性、无流动性时必定恢复、跨片结算或跨AZ/多机HA。
- 不覆盖风险公式、完整PM、保险基金/ADL、生产容量、长稳和真实资金签批。**生产仍NO-GO。**
