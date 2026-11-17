# 连接生命周期归因与本轮不启用 session 的决定

本组固定代码基线 `adadffc3e71163967c02114f81a871a2ae75f674`，只读取已有合成证据。
没有运行新负载、SQL probe、worker 或真实作业，也没有改 `Database`、guard、交易或
worker 的运行代码。没有增加 `_connect` 参数、session API 或开关。

**本轮暂不批准金融连接复用实现。** 连接路径存在可观测时间，但现有证据不能确定缓存与
批处理之后仍可独立节省的金融连接成本。不能把 profile 的整块累计时间写成收益。

## 证据身份与计时口径

原实际子进程 profile 来自 `7200097ce9f92fa678907bee9a99933f60d65bc3` 的 P1：
worker0 PID57001、worker1 PID57002；目录与原哈希见
[原 P1 manifest](../benchmarks/results/20261117-managed-corrected-7200097/raw/P1/manifest.json)。
新 [只读分析工具](../tools/analyze_connection_profiles.py) 先核对该 manifest 及原 profile
字节，再读取其标准 pstats 数据；不 import 金融模块，不访问数据库。
[完整派生输出](../evidence/runs/connection-profile-attribution/attribution.json)保存原哈希、
调用者边、角色计数假设和无法确定的字段。

profile 包括启动、等待、I/O 和关闭，不是纯 CPU 数据。cumulative 项相互嵌套，禁止
将 connect、execute、guard、risk 与 COMMIT 的累计值相加为可消除时间。两个子 profile
没有 self>cumulative 异常；父 dispatcher 有五项，因此不用于父线程耗时精确归因。
原 P1 本来是短接纳诊断，没有撮合成交；本分析不会改变原稳定性/容量否决结果。

## 连接角色与 close 的可验证拆分

| 720 观察项 | worker0 | worker1 | 可以推断的范围 |
| --- | ---: | ---: | --- |
| base `_connect` 调用 / cumulative 秒 | 1037 / 1.021442 | 959 / .954067 | 各种 base 事务角色合计 |
| 所有 SQLite close 调用 / self 秒 | 1480 / .599726 | 1465 / .544542 | 包含额外 router reader |
| `_role_transaction` 直接 close / self 秒 | 1037 / .584437 | 959 / .522932 | 只有 base 事务关闭这条 caller 边 |
| 其他 caller close / self 秒 | 443 / .015289 | 506 / .021610 | `_state`、funding claims、control 打开 |
| `_connect` 直接 execute / self 秒 | 4134 / .865928 | 3822 / .815898 | 连接配置 SQL，已包含在 connect cumulative 中 |

原 720 的 storage 包装器各 yield 一次。在本次正常完成的 profile 中，每个完整包装器
有两次 generator resume；据此得到下列**计数估计**，并可与实际 connect 数完全对齐：

| base 角色 | worker0 估计完整 context | worker1 估计完整 context |
| --- | ---: | ---: |
| financial | 1022 | 943 |
| read | 7 | 7 |
| control | 8 | 9 |
| inbox | 0 | 0 |
| 合计 | 1037 | 959 |

这些不是逐笔事务日志。特别是，所有角色的 connect/close 都被聚合到同一个
`_role_transaction` caller；pstats 不保留 role 实参、每次调用区间或文件描述符身份。
因此金融角色专属的 connect/close 秒数仍为 unknown。不能按调用比例分摊，不能把
1.021+.584 秒或 .954+.523 秒称为 session 实测可节省时间；未来复用还必须保留文件身份、
权限、租约和完整 guard 检查。额外 router reader 也不属于金融 session 的作用范围。

## 与其他路径及已实现候选的重叠

| 原 P1 路径 | worker0 次数 / cumulative 秒 | worker1 次数 / cumulative 秒 |
| --- | ---: | ---: |
| SQLite COMMIT | 1037 / 1.199359 | 959 / 1.174754 |
| guard constructor | 1037 / 1.122722 | 959 / 1.117631 |
| before_commit | 1037 / 1.730493 | 959 / 1.615702 |
| data guard 校验 | 2919 / 1.725316 | 2647 / 1.631021 |
| control schema 校验 | 2068 / .642875 | 1912 / .633955 |
| 账户监督 | 711 / 5.847457 | 586 / 5.031561 |
| risk | 861 / .753060 | 758 / .695967 |
| QueueStore process_one | 187 / 1.877135 | 213 / 2.070623 |
| JSON dumps | 4630 / .060103 | 4405 / .065527 |
| JSON loads | 2653 / .056689 | 2518 / .054014 |

队列的累计时间包括事务、guard、风险和空轮询；不能把它当作纯调度 CPU。`execute`
包含 SQLite 工作和等待，guard 及 risk 又各包含它；JSON 值也不是可直接叠加的占比。
父队列的计划到达至 enqueue 等待约束还不能靠子进程 profile 归因。

| 已有候选 | 针对的成本 | 仍须保留或新增的成本 |
| --- | --- | --- |
| normal supervision cache，评估参考 `fdbd95b` | 证明有效的 NORMAL 命中可避免整次监督写事务和 risk | 完整 RO 依赖证明、原始行情年龄检查；miss 的原完整金融路径 |
| durable batch，本代码基线已有 | 多条执行共享一个金融事务，可摊薄该事务的连接/guard/COMMIT | 独立 manifest metadata COMMIT、逐命令完整 risk/audit、全部原 CID 恢复；实际执行可能只有0/1 |
| 金融连接 session，尚未实现 | 理论上针对剩余金融连接配置和 close | 每笔真实 COMMIT 与全部 guard 不可省；原子结果恢复、连接所有权与清理复杂度新增 |

三个候选的潜在收益重叠。cache 消除事务后，它的 connect/close/guard/COMMIT 已全部
不再发生；batch 减少事务后相同成本也可能被摊薄。不能从旧 P1 各取一份累计时间加成
预期提升；应先在同一新已验源码上量测 cache/batch 的实际命中、执行前缀和剩余成本。
NORMAL cache 默认0、batch 默认0，候选正确性测试不等于本表有性能收益证明。

旧 [idle WAL keeper 实验](storage-performance.md)三组均值约提升3.2%，P99无稳定改善，
已经否决合入。它只保留额外 idle reader、每笔仍开新业务连接，既不证明新金融 session
也只能提升3.2%，也不支持从旧 profile 推导15%等未经测量的新收益。

## 下次行动与实现前置

先完成 cache/batch 同源码资格与实际对照，再记录**按角色、按阶段**的 connect、配置 SQL、
COMMIT、close 调用及区间，分别报告原入队持久提交、金融提交、manifest、背景和控制。
需要新的小组件测量时，先限定最多100个合成事务、单CPU、最多2秒的独立计划；该计划
本轮未运行，也不是订单/撮合容量验收。两个子 profile 的现有调用边可作为对照，父端
另需正确的逐线程计时，不能修饰旧混合线程数据。

只有残余成本支持之后才考虑独立 session 原型，且必须先证明：

1. financial 连接不向 read/inbox/control/batch metadata 提供已编译授权语句；原生 UDF
   每次 DML 和最终 fencing 检查仍真实执行，不凭 Python role flag 判断缓存语句安全。
2. 连接严格归属 PID、线程、token 与 inode；keeper 的浅 copy、`for_writer`、旧 token
   和换代对象不能共享连接。idle 时不能接受遗留裸 handle 的普通操作。
3. `_BoundShardDatabase` 每笔 shard/layout 检查不被包装器绕过。拒绝 subclasses 的
   独立原型本来就不能宣称已接入当前实际 worker。
4. 每笔仍 FULL 真 COMMIT；COMMIT 后异常不作为未发生，不能透明重试。出错后连接
   必须停用或关闭，原 CID 由持久状态恢复，不因 session memory 判断结果。
5. shutdown、异常和进程死亡可释放自有资源，无 ResourceWarning；不增 TTL、不关闭
   audit/完整 schema 校验、不使用 live immutable，不恢复已过期 authority。

本交付仅增加分析工具、派生证据和决定记录，没有部署或数据迁移。回滚可删除这些新增
文件；现有连接路径、资金、业务 ID、生产开关和原始证据均不改变。生产、长稳、持续
10,000/s、HA 和真实资金批准全部保持 false。
