# 三个资金费纯算术方法的独立 once 封装

本变更只准备 `FUND-EXEC-001` 的执行闭包，**尚无 root 执行授权，目标尝试为零**。
原 `f3410774c556673fdccb39c742b55100c0fd31d9` 的两个金融模块、全部六个测试、
部署回滚说明和公开来源摘述均保留原字节。原计划及 runtime manifest 另有精确
`*-f341-NOT_RUN.json` 副本；原阶段保持 NOT_RUN，不是测试失败。

固定入口为 `tools/run_funding_pure_once.py`，仅接受经复审的 plan SHA 和完整源码提交。
`pure-once-plan.json` 列出 64 个原运行/测试输入加一个控制文件，共 65 个 byte pins。
父进程先核 actual HEAD、plan SHA、每个物化 regular/canonical 文件和 Git blob，
再建立新 `/workspace` 子目录（0700/O_EXCL 文件0600），形成保留 bytes capsule。
目标自 capsule 校验后编译控制文件及固定目标源码，不再从活动 checkout 取得执行输入。
运行后的源读取只是复核。这个边界依赖可信不可变源码，不是远程证明或恶意代码 OS sandbox。

固定 selector 只有以下三个，且 inner 同时核 plan 与硬编码 tuple：

- `FundingArithmeticTests.test_two_sides_negative_and_zero_rates_use_manual_cash`
- `FundingArithmeticTests.test_three_accounts_need_real_segregated_rounding_capital`
- `FundingArithmeticTests.test_invalid_inventory_and_decimal_context_do_not_change_policy`

不使用 discover，也不选择任何 `FundingLocalSQLTests`。执行输入只有
`uta/__init__.py`、`uta/perpetual_funding.py` 和原测试模块；控制文件也从保留 bytes
自引导。其余 61 个金融运行输入只是完整版本的保留与字节校验，不加载为服务。
包的搜索路径为空，不能回落到文件系统加载其他 UTA 模块。

SQLite 模块 import 本身是元数据，不等于连接。审计 guard 拒绝 `sqlite3.connect`、
进程、网络、PID/signal 和 authority/proc 打开；线程入口也被拒绝。固定审查源码下
不连接数据库，不启动 worker/线程/服务器。guard 不声称抵御任意敌意 native 绕过。

父进程和子进程均绑定 CPU1；唯一 target 是绝对 Python3.12 的 `-I -S -B`，由
`timeout --signal=KILL 10s` 拥有终止；另有最多两秒 drain/完成分类窗口。
只读 Git/source 准备不算业务预热，不算三个方法耗时。12秒是父级完成分类检查，
不能中断阻塞的文件读取/fsync；调用者必须另外记录实际 outer 退出与完整墙钟时间。
不能由 inner/END 自证未来 outer exit0，也不能把 inner elapsed 报作端到端延迟。

bootstrap、taskset、timeout 与子进程 Python/native FD1/2 统一进入父级双 pipe。
一个共享 32KiB 计数器在写入前扣额度，保留512字节 trailer；短写/溢出 sticky125，
不退款、不续写 payload，只 drain 后记录 UNKNOWN，不能截后 PASS。控制/capsule 文件
在创建写入前计费，单独保留 child control1MiB 和 raw32KiB，使已知写入路径的逻辑
文件长度合计不超过8MiB。这不是 kernel 磁盘配额或内存上限。

PASS 要求实际 host wait/reap、双 EOF、原 BEGIN/END、三个方法零失败/错误/skip/
expected-failure/unexpected-success、源与 plan 前后相同、当前 CPU1，以及及时 TAIL。
还必须由 caller 观察真实 outer exit0。任何缺失、超时或不确定均保第一原件，不重试。
异常首轮不改变原 f341 的未运行状态；后三个 SQL 方法、五个 SQL authority、调度、
未完成义务登记、运维鉴权、managed/HA 与生产审批仍为独立 OPEN。

部署/回滚仅停止这个新控制入口并保留所有旧规则、authority、原件和已确认分录。
本变更没有数据库迁移、产品启用、默认路由、目录或金融计算变化。
