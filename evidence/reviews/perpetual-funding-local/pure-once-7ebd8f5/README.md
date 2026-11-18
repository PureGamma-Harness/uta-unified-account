# 固定三条资金费纯算术：首次 once 证据候选

冻结源码 `7ebd8f5fa17d4c339956bbe4e5f04a529d83a8a4`，plan SHA
`92c452306d90fd321b077afe7a02ee5019f9d36522d96f14f74a926d52b17f3c`。
root 单独授权后，仅执行 literal-argv 所列固定三条 Arithmetic 方法一次，未重试。
本目录是待原独立验证组核验 RAW 的 SAFE 候选，尚不代表独立验收已闭合。

三条测试均通过，failure/error/skip/expected-failure/unexpected-success 为0；SQL连接为0，
未选择三个 SQL 方法。65 个原输入/控制 pin 合计1,361,582字节，执行前后相同。
实际 runtime 为 Python3.12.14、指定解释器 SHA、CPU1、`-I -S -B`。
caller-actual-exit 与原 raw 记录实际 outer exit0/wait/reap/双 EOF；outer-END/TAIL
必须与这些 caller 事实联合检查，不能自行证明未来退出。

时间分别记录：inner10,205,818ns，owned target/drain276,367,950ns，调用者观测
outer 完整进程552,651,830ns。inner 耗时不是端到端容量结果；这不是性能验收。
raw 合计10,501字节，无截断或短写。只导出逐项 allowlist raw、有限投影及原件
长度/SHA清单。完整 source capsule 和其他私有原件留在原 namespace，不公开。

原 f341 全六方法计划以及49407/d7e0历史文件仍为原字节 NOT_RUN0，不改写历史。
三个SQL方法/五DB、未完成义务、scheduler、opsAuth、managed/HA、金融独立验证及
生产审批仍 OPEN。资金费本地原型的部署和回滚约束沿用原说明；本证据不启用产品、
不修改 authority、不修改数据库、路由或金融代码。回滚停止新测试入口并保留原件。
