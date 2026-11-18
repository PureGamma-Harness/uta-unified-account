# 前缀因果顺序与真实输入预检：修订设计

本修订针对固定 `9f74dce34fd856fc2bc6e04b6c310a30e93ec10a` / 首证据 `3b0a9ab0d9b8ed9719dad0328076aa5b17a1bdc0` 的独立审查缺口。独立源码 `12f6ff9b75725c1837714d48f33d06dcff15dfe7` 与首 OWN `17e4542f3c69a61feaa421b4284183d323ff4e19` 已确认 **4 PASS / 4 RED**，0 ERROR，exit 1，109,582,576ns；三个中间账务因果反例与一个 v1 limitations 未注册标签反例均成立。全新 N3/K2 literal fixture、零 genesis 独立 oracle 和所有首原件完整集成，未覆盖作者原 25 项、19f 规格或 d243 首终态。

## 初始条件与因果规则

当前纯 profile 的 ledger 从零起始，三个 USD deposit、一个 BTC deposit、pool funding 和唯一初始借款全部显式存在。credit 客户原有 1 BTC **现金资产**不等于初始本金负债；该 profile 的借款前本金债务为零。将 REPAID 放在唯一 BORROWED 之前，即使后面借款/最终 gross 余额抵消正确，也可能制造中途负债反号。

这不是“任何账户还款早于新借款都违法”的通用规则。若另一个账户快照自带旧本金负债，其先还旧债可以合法；那需要新版本 profile 和被验证的 opening-state，不可套用本 profile 的零初始负债假设。纯输入不得以省略 snapshot 或更改 N/K 来隐式切换初始条件。

修订逐事件维护独立 owner/asset projection，在每个 journal event 之后核对：本金 liability 不为正，应收不为负且严格相等于本金债务；pool 可用 BTC 和 customer 可用 USD/BTC 不为负；费用应收不得通过未来事件垫付；system custody/capital 的 backing contra 分量允许原定义的负数。这是本合成 profile 的有界规则，不改变 UTA 一般破产/信用账务政策。

同时核对 managed workload 的拓扑顺序：全部六个 bootstrap 义务完整后才出现 round 业务；每轮两侧 open fee 终态后才进入 close fee，两侧 close fee 完整后才出现该轮 repay，前一轮 repay 后才进入下一轮。每一对 fill 内不强制 buy/sell 的任意实现顺序。所有依赖使用原明确 business ID 和 round/step 关联；不得仅按最终 totals 或输入排序推断。

limitations 的版本边界应使用固定 19f schema 的完整枚举，未知标签按不支持版本拒绝；不靠“保留两个 required 字符串”接受任意新含义。该规则仅约束合成声明形状，输出仍不能授予实际审计、quiescence 或生产资格。

新增 focused 批次最多 10 个 methods，复用已审独立文件的纯 literal 定义及 oracle，不调用其原 8 个 test methods，也不重跑作者原 25 项。涵盖三个已证因果负控、未知枚举、合法入金交换、合法每对 fill 双侧交换、完整合法 false-authority 结果，以及 fixed workload 内 close/repay 次序与不支持 opening-state 的边界。代码冻结后再按 root 的唯一 CPU1/10s 预算执行，首次结果全部保留；当前尚未执行本修订测试。

## 真实只读输入前置的具体交付物

下一输入阶段需要独立的 `quiescence-attestation.v1`，至少列出原 source/boot/job、已封存父子进程 lifetime 与所有账户/router/shard writer 清单、原 fencing generation、所有写入路径与失效证明、原投递器/撮合接入的停止边界、未决业务义务清单及独立批准引用。单个 driver 已退出或 audit namespace 只读挂载不能替代 writer 闭包证明。

该 attestation 与 database-set manifest 分开：manifest 对 checkpoint/router/shard 主库和实际 WAL/SHM 的存在、dev/inode、大小、hash 与原 job 文件身份作绑定，记录缺失与未知，不能把非空 WAL 当无用 cache 丢弃。认证与真正隔离由独立审查的执行环境提供，纯函数不能通过 caller true 或自算 hash 证明。

未来 reader 的可审代码入口必须先接收确切批准的 manifest 和 attestation，再验证 kernel 对原数据只读、private-output 可写、预算充足及无法绕过的单次执行标识。只有所有前置闭合，才可开启只读 SQLite 并创建独立完整私有副本；非空 WAL 的一致读取方案须先在新合成库做故障验证。需要原 SHM 写入、无法冻结全部 writer、跨库水位矛盾或未知 action 时必须拒绝，不启动修复、checkpoint、恢复 worker 或新 generation。

新 reader 第一里程碑应在临时合成三库而非旧 909 上验证：存在/缺失/非空 WAL、未知 writer、PID 重用、磁盘不足、复制前后原 hash 改变、跨库 logical head 不一致、重复命令及进程中断。测试预算、source、clone 路径、CPU 和总时限由 root 逐次固定授权；当前设计没有执行任何 SQL、原数据读取、clone、observer 或审计，也没有发行旧 strict cold receipt。
