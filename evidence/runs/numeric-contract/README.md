# 独立数值标准的原始证据

固定 clean `3c4f553c26b0817acac65fdc9f430fcb73bae404`，三运行时各10项通过，
CPU0顺序执行，`-W error::ResourceWarning`，未观察到该警告或ignored exception。
Python3.12/SQLite3.53.1实际进程.447s；Python3.10/SQLite3.53.1 .446s；
Python3.13/SQLite3.46.1 .455s。manifest逐项保存source before/after、原命令、Git状态及
原日志hash；这些是小型定向测试，不是完整发布资格。

initial-python312是开发阶段未提交test定义的原件：10个测试，PnL gain/loss两个子例
KeyError，原因是测试误读payload.order_id；实际事件字段payload.order.order_id。
fixed-development只修测试读取后通过，早于新增的fresh DurableLedger重开断言；不把它
冒充最终source。三个不带development字样的运行时日志才绑定精确3c4f提交。
所有记录均原字节复制，copies列原路径、大小及hash；run_matrix是实际driver原件。

运行时代码相对4060429完全无变化。整数/币种精度、PnL/fee舍入、18位信用与8位存款
入口差异及展示ratio的人工标准见docs/numeric-contract-independent-review.md。
没有真实产品/容量/长稳/跨片/HA通过结论，production_approved=false。
