# Managed RO API 的独立账务验证

验证文件是 `tests/test_managed_views_reference.py`。它独立构建合成账户，经公共信用接口和真实双腿 `Matcher` 执行，再用无 writer token 的 reader 与实际 loopback HTTP 查询；预期值不调用生产 risk、reserve、fee、cost-basis 或 amount formatting helper。金额预期用手算常量及独立十进制字符串到整数 minor-unit 的解析器。测试与本文不修改运行时代码。

## 冻结来源与发现

工作树从 root `57d776c` 开始，加入 readiness `0dd6042`、RO API `cbe6516`。测试并发前明确加入 root 已修复的 storage/startup/read-boundary 依赖 `dabbeeb`、`97b7967`、`99e347b`，以及 diagnostics reader 修复 `e0c45af`、RO reader 修复 `1ed207a` 和独立 HTTP diagnostics adapter `ed9a6fd`。最终还加入基础只读连接的 `89bd349`。这避免把已知存储缺陷混报为新的业务接口失败。后续修复及最终执行结果记录在本文件末尾。

实际发现三项，并由实现者维护 runtime 修复：

1. 原 `cbe6516` reader 在目标 SQLite inode 上 raw open/fstat/close，会释放同一 PID 中其他 connection 的 POSIX 文件锁。独立 case 先保持一个真实 SQLite read snapshot，并持有由另一 PID 检测的 kernel lock；读取前另进程返回 blocked=7，载入实际 `git show cbe6516:uta/durable_views.py` 后同一 case 读取后返回 acquired=0，断言 `0 != 7` 明确失败。相同 repaired-storage 环境的 `1ed207a` 以 stat + SQLite `mode=ro` 读取，原断言通过。这个辅助 byte-range 锁验证 close 的内核行为，不把账单投影当作完整数据库锁协议证明。
2. 原读取会接受 Python `Decimal` 的非标准词法，并返回不符合资产最小单位的借款。用合法离线 token 注入 `principal='1_0'` 或 `'0.000000001'` 后，BTC scale=8 的响应仍成功。独立两个 methods 共 13 个反例全部实际失败：本金/利息/cost_basis × 下划线、空白、Unicode 数字，以及本金/利息 × 十进制/科学计数的 1e-9。期望统一为 503 `view_data_invalid`，合法 `1.0E-8` 必须继续接受，不能用 exponent 的简单比较误拒尾零。注入只验证故障读取，不代表这些输入通过公共信用入口。
3. 合法离线 token 插入 JSON payload `{"amount":1e999}` 后，原 reader 返回 `inf`，实际 HTTP 序列化失败为 500；`-1e999` 也失败。独立测试要求 direct 与 HTTP 均明确为 503 `view_data_invalid`，且不改写数据。修复 `8da82df` 在 parse_float 阶段检查有限性，正常有限 JSON float 保持兼容。它不把标准 JSON 的巨大 exponent 默默变为非有限输出。

## 可手算的财务事实

USD scale=8，初始客户现金 `100.00000003`，费率 `0.0004`。每一行都是实际两账户配对成交，maker 限价即成交价；没有用 market tick 假造成交。

| 客户执行 | 实现 PnL | 手算费用 | 剩余有符号数量 | 剩余有符号成本 USD |
| --- | ---: | ---: | ---: | ---: |
| 买 0.3 @ 100 | 0 | 0.012 | 0.3 | 30 |
| 卖 0.1 @ 103 | 0.3 | 0.00412 | 0.2 | 20 |
| 卖 0.3 @ 99 | -0.2 | 0.01188 | -0.1 | -9.9 |

现金为 `100.00000003 + 0.3 - 0.2 - 0.012 - 0.00412 - 0.01188 = 100.07200003`，即整数 `10_007_200_003` minor units。客户 statement 逐笔相加必须等于这个整数，raw ledger balance 也必须相同；全量账务逐资产整数和仍为零。

另借入 BTC `0.1`、应计利息 `0.00000001`、还款 `0.00000002`。先付利息一个 minor unit，再付本金一个 minor unit，预期 BTC 现金 `0.09999998`、本金 `0.09999999`、利息 `0`。响应必须分别保留这些 gross asset/debt 数值，不做价格换算或相互净额化。

scale=0 的 WHOLE 资产显示 `7`；scale=18 的 ATOM 账务投影显示负三个 minor units：`-0.000000000000000003`。后者用平衡的合成账本 posting 构造，只验证已存账务的精确读取；当前存款业务入口有八位小数上限，本测试没有声称可通过该入口存入 1e-18。两种全局 Decimal rounding、precision=1 和 Inexact/Rounded traps 下，所有被验证的货币响应与基准完全相同。

实际并发 partial fill 还覆盖另一组手算事实：原 short -0.1、cost -9.9，买入平 0.01 @ 100，PnL=-0.01、fee=0.0004；新现金为 `100.06160003`，仓位 -0.09、成本 -8.91。在 reader 已读取 snapshot metadata 后，另一个线程真实 COMMIT 此 fill，当前响应的旧 ledger 和 metadata 仍完全一致；下一响应才能同时看到新 version、水位和现金。没有把不同 HTTP 请求冒称为同一个数据库 snapshot。

除 reference policy 外，另用实际 configured Cross catalog v11/rules v13 执行借款、本息还款、订单和 fill，验证 `phase1_cross` 内容引用及 owned 历史决策保留真实 catalog/rules 版本。读取期间禁止金融 constructor 和 `ExchangeService.risk`，不把只读接口的 `unsupported` 风险状态升级成重算结果。

## 读取、隐私与重建边界

- 实际 HTTP 验证 reader/funding 的 scope/role 拒绝先于查询；单订单、私有事件、决策和 statement 不泄漏另一客户 ID、对手订单、system contra account 或本机路径。客户 statement 只含自身 postings，不能据此宣称独立验证整个双记账 journal。
- 事件/ledger 在 limit=1 时排尽固定 `until`；其他账户和全局 market 更新产生的序号空档不丢项、不重项。排尽后游标推进至 `until`，空的私有增量也能跨过新的全局序号。order/position 是当前投影，账户版本改变必须 409 并重建；一致 SQLite backup 的 inode 替换也必须改变 stream 并要求重建。没有把 rowid 当永久 change stream。
- 验证所有表在正常读取、404/403/400 和 risk 501 前后 byte-value 相同；禁止调用金融/账本 constructor 或 acquire writer token。不存在/空 financial 文件不创建 schema、WAL 或 SHM，也不被修复；已有 DELETE journal authority 在读取前后整个文件 bytes 相同，不被切回 WAL。当前 quote 缺失时不能改用历史 archive 冒充当前行情。
- 两个真实 spawn PID 经 HTTP 验证 partial publication 的本片报价可以 fresh，但全局 `financial_ready`/`ready`/`dispatch_available` 仍 False；完整发布并激活后为 True，自然过期后 PID 仍活而就绪 False，新版本发布激活后恢复。另在实际 control EX gate 争用下验证有界诊断返回 `control=None`、unknown observation 及未就绪。该 fixture 的租约是 3 秒，长于刻意造成的 1 秒诊断争用；未更改生产租约。
- quote 的未来 -1 秒及最大 age 相等边界保持原政策，跨出边界明确 future/stale；只读响应保存原始 observed_at，不包含虚构的风险通过字段。`/risk` 明确 501；未计算或验收实时 equity、IM/MM、reserve、可借/可提、PM、feed authenticity 或 WS delivery。

账户版本与 market/policy 内容引用都应由客户端比较。单个请求的一致性不使跨请求账户、仓位、statement、事件或不同分片自动拥有同一原子 snapshot。没有外部财务规则负责人或生产签字在此被代签。

## 执行记录

- 修复前 kernel sentinel case：实际 `cbe6516` reader 原源码在 repaired storage 上红，1 项 FAIL（0.217s），读取后探测器从 blocked 变 acquired。
- 首批 14 项在 `1ed207a` + storage/startup/diagnostic 依赖 + `ed9a6fd` 上通过（6.398s）。
- 新增语法/scale 两项在修复前实际 13 个 subcase FAIL（0.494s）；`66fdab3` 上不改原断言后通过，不降级为 skip/expected failure。JSON overflow 两个 subcase 在修复前也实际 FAIL，`8da82df` 后同断言通过。
- 最终独立文件共 20 项，在已列修复依赖上首跑通过（7.278s）。它们是合成工程验证，没有替代生产流量、外部财务规则签字、feed trust 或 G7 放行。
- 最终源码（含 `66fdab3`、`8da82df` 和 `89bd349`）整合独立 20 项、实现侧 RO 18 项、HTTP diagnostics 3 项、process readiness 12 项、storage snapshot 9 项：Python 3.12.14 / SQLite 3.53.1 为 **62/62，19.270s**；Python 3.13.5 / SQLite 3.46.1 为 **62/62，19.069s**，后者启用 `-W error::ResourceWarning` 且输出无 warning。没有 skip 或 expected failure。

```sh
PYTHONPATH=tests python -m unittest test_managed_views_reference test_durable_views test_durable_diagnostic_adapter test_process_readiness test_writer_fence_snapshots -q
PYTHONPATH=tests /usr/bin/python3.13 -W error::ResourceWarning -m unittest test_managed_views_reference test_durable_views test_durable_diagnostic_adapter test_process_readiness test_writer_fence_snapshots -q
```
