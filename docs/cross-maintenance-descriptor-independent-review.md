# 维持保证金夹具描述符修复：独立 CODE 审查

结论：`CODE_CLOSED_FOR_SCOPED_PURE_ONCE`，仅适用于新的六方法纯算范围。
审查源码为 `b4e1b5907e6b64578d39614f87c866d7f4f65631`；新目标执行次数为零。
未 import、compile 或执行目标，未执行 SQL、进程探测、撮合或基准。
本次仅解析 JSON/AST、读取源码与 Git 字节、检查常规文件及哈希。

新计划 SHA-256：
`021639834b185c8e944d180919d082e5301d6d6b0d0397b2e49f036961d39416`。
九项输入共170187字节，均已核对 owner 工作树中的 canonical regular file、
Git b4e1b590 原文和计划长度/SHA；计划物理字节也与 Git 一致。

## 缺陷与修复

真实 `ExchangeService.product_catalog`、`portfolio_rules` 是无 setter 的
`@property`，分别读取 `_product_catalog`、`_portfolio_rules`。原夹具直接赋值给
前两个属性，而原纯算程序只保留六个选定方法，未保留这两个描述符。这使旧的
抽取类拥有普通可写属性，并不能证明真实 service class 的夹具兼容性。

本次测试修复仅初始化实际 backing fields，随后断言两个 getter 返回对象身份，
并断言向真实只读属性赋值抛出 `AttributeError`。新计划将两个原始 property
FunctionDef 节点加入选定名单，原 driver 的 AST 选择逻辑保留完整 decorator/body，
没有添加 setter，也没有为测试制造另一种属性行为。

六个测试方法的 AST 与首次公开源码 fc2d574d 完全一致；15个 completion IDs、
人工预期、six financial/helper methods 和 future annotations 保留原范围。
driver 与402c784原纯算源码逐字节一致；从首次公开源码 fc2d574d 到本修复，
所有 `uta/` 运行时代码差异为零。

旧计划以 `once-plan-402c784-first-original.json` 另存，逐字节等于首次公开源码中
原 `once-plan.json`，SHA-256 仍为
`92fc36f7c1ea2f98d91f518fe93667c4a8ad907600a8e32c0070631c34fdcdc6`。
旧402c784纯算 PASS 保持其实际的“省略描述符的抽取类”范围；本审查不将其改写为
失败，也不将其升级为真实模块单元测试通过。首次 CI 的4ERROR及8个 unit job
失败属于集成负责人与交付文档提供的背景，本次未读取其 private 原始日志，不能
声称独立核验了那些原始 CI 数字。

## 一次纯算边界与未验收项

计划保留同一固定 Python3.12.14 二进制 SHA、`-I -S -B`、CPU affinity `[1]`、
GNU `timeout --signal=KILL 10s` 和六个固定方法。共享 stdout/stderr 预算为
262144字节，其中512字节为失败 trailer；driver 在 FD 写入前计入预算，短写或
超额直接退出125，不重试。源码验证前后读取九项保留字节，案例完成列表必须与
15项计划完全相等才会形成 scoped PASS。

实际程序只装载六个内存风险模块与所选 service AST，构造器、`_admit_order`、
`_apply_fill`、SQL、原始 service imports 和进程控制路径均不进入该范围。
选定模块的静态 import 清单已记在机器可读审查记录中。无 target child、worker
thread、network、SQL 或 PID/proc/pidfd/signal操作被本纯算范围授权。

driver 的 source commit 字段只是 invoker label，不能替代调用方 Git 绑定。
Root caller 仍须在执行前将计划和九项实际源字节绑定到 b4e1b590，使用全新私有
输出目录，保存真实 argv/intent、monotonic start/end、FD EOF、实际 exit/reap，
并验证 END 与外层结果。10s硬期限由 caller 提供，不能把 inner receipt 当作
caller 已退出的证明。首次失败或 UNKNOWN 应保留原始结果并停止，不自动重跑。

本结论不是执行授权。新纯算、normal-module unittest、CI、RAW独立复核、服务准入、
真实成交、SQL恢复、吞吐、HA及生产验收均未在此执行或新增证明。先前 SQL 三库
结果没有因本次测试修复而被修改，也不借用为本次夹具的执行证据。

机器可读记录：
`evidence/reviews/cross-maintenance-descriptor-independent/CODE-review-b4e1b590.json`。
