# Existing-service factory 独立复核

复核实现固定为 `a339c1c2b3b731387259839e1562c2c272d56140`，含作者 factory
`bf746b1e7f5437f20fc1f953d7023b3d59615720`、其父级集成 `e94843c`、作者负矩阵
`2348159` 和 V2 hook。独立组在单独 worktree 新增测试，未改实现、复用作者 fixture、
创建假 authority、改旧作业或运行服务。当前复核范围未发现阻断问题。

独立测试先提交于 `6a066d5dd63c5960609b1679dca8eb66d9e62886`，之后唯一一次真实批次
2026-11-17 14:30:35.016111–14:30:35.484053 UTC，CPU4/Python3.12、合成临时目录、
ResourceWarning 为 error，七项全通过，unittest 0.282 秒，进程 0.467947 秒，未超时。
没有失败后重跑或扩大循环，详细命令、退出码及实现文件 hash 在原始 manifest 中。

- 真实 public constructors 创建账户、100 USD 资金和 10 USD 信贷池。成功 factory
  恰开一条连接并关闭；构造 trace 无 DDL/DML，返回对象使用确切原 Database。
  后续真实存款后，对象重新开连接读取 101 USD，不持有已关闭快照。
- 原真实 WAL read snapshot 建立后，另一条真实 financial transaction 成功提交
  1 USD 存款；factory 在原 snapshot 验证精确 100 USD 和两条 journal event。
  snapshot 结束后的新事务读取 101 USD，未混合两个逻辑时点。
- 缺失固定 credit trigger 时，唯一构造连接关闭，所有坏源 logical schema/rows
  原样保留，无 repair。名为 `audit_credit_decoy` 的额外核心表 trigger 被精确拒绝，
  audit 前缀不构成豁免。
- read 事务中真实被 authorizer 拒绝的 DELETE 被调用者捕获后，factory 仍拒绝同一
  poisoned context，事务终结保留同一个拒绝对象，未通过捕获异常恢复权限。
- 真实 base fence acquire 后可只读构造绑定对象；实际 release 提交后，旧 token
  立即被 constructor 拒绝，无假时钟或手动改 lease。
- 重建后的真实 base-managed CreditService 的 public borrow 仍返回
  `unsupported_credit_operation`501；全 logical schema/rows 无影响。

独立静态复核确认 read/control join 绑定确切 Database、connection、线程、活动事务及
未 poison 状态；实际已绑定 token 会在该 snapshot 检查，后续金融写仍独立 fencing。
三个真实公共 constructor 不用 `__new__`、假 startup 或 verified flag。固定 schema
比较覆盖全部约束和列，辅助 trigger/index 只能由实际 `_load` 验证后的精确编译 inventory
放行；schema3 的真实 current-build base artifact 缺失不会回填，policy 歧义拒绝。

另以原 factory 前基线 `143fe601f2058b87f9a9dfb431954c2efc174e0f` 独立纯 AST 比较：
仅去掉新增 existing 参数/分支，三个默认 constructor 与原完全相同；`_repay`、public
repay、`_record`、`_prepare` 完全未改；从 exposure guard 到原 credit receipt 的 borrow
金融计算尾部，仅增加 dedicated audit completion，原数学 AST 不变。脚本和结果保留。
这证明所比较路径的代码兼容，不代替完整回归和端到端验收。

V2 native capability、实际 successful borrow、第一条 producer source COMMIT、FIFO
操作完整闭合、成功重启、unknown receipt 与独立金融 oracle 仍未由本复核运行。
`a339c1c` 的新格式2 hook 缺少原生 scope 仍关闭，其他 corruption 不降级为501；静态
检查不能赋予尚未安装的完整 V2 owner 正向验收。此报告不签署 V2 restart READY、
生产可用、万笔容量、多节点 HA 或真实资金启用。没有部署/数据迁移动作；回退应保持
公开入口关闭，不得删除已发布 capability 或资金历史实现降级。

原始记录：[独立证据目录](../evidence/reviews/credit-existing-factory-independent/)。
复跑命令见 `first-manifest.json`；pure AST 可执行目录内 `verify_compatibility.py`。
