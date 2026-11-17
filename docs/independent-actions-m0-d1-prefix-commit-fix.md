# D1 完整 prefix 的提交与发布修复

独立首反例 f605b96c4714c744b65403bbfe3861f68f62d768 已完整保留于本分支的 fe9a924。3e586 的完整 JSON 在 fsync EIO、隔离 rename PermissionError、删除 PermissionError 后仍留 public，writer 虽返回 UNAVAILABLE，collector 却把它当合法记录发布。原首 RED 与原 154 PASS 均不改写；此缺口涉及诊断发布，不代表资金路径放行或原 UNKNOWN 升级。

新 writer 在两侧 owner-only 目录确认后，以 private/resource-diagnostic-incomplete-PHASE.json 的 O_EXCL/O_NOFOLLOW 0600 文件保存唯一候选。write、flush、fsync 以及 context close 全部成功后，才执行 os.link(incomplete, public_name, follow_symlinks=False)。硬链接不覆盖已有首记录；文件系统不支持、权限、写入、fsync、close 或 link 失败均不改用其它协议，不重试，不放行 primary。private staging/incomplete 名称、part 名称和 staging 目录都不是 public allowlist 路径。

完整但未成功 fsync/close 的 JSON 只留 private。public 不出现其文件名，collector 无法单靠语法把它重新解释成成功记录。可选私有 alias 删除失败发生在成功发布之后，不撤销已发布记录；两条实际路径均计入原 cleanup，可能保守重复计量，不给出新磁盘额度。写前预留 2×record bytes，覆盖 link 后两条 alias 同时存在及删除失败，不增加 cleanup 32 MiB。既有 private incomplete 文件不覆盖；public 首条不覆盖。调用依赖 main 已存在的 exclusive 新输出根，不提供旧 3e586 输出目录的恢复/升级协议。

collector COMPLETE 的含义仅为已有 public 记录完成验证；public 为空时亦可 COMPLETE，不证明每次诊断写入成功。实际 writer 失败仍通过 ResourceHealthFailure.diagnostic_status=UNAVAILABLE 及 parent phase status 保留，primary/cause/context 不变。空 manifest 的 allowlist 通过不等于诊断已交付，更不会改变金融 UNKNOWN。若 public 有坏/未列文件，仍由原 allowlist 拒绝。

九字段 schema、4096 bytes 上限、first-per-phase、原四条 closed streams、64/96/32/192 MiB、3 次/50 ms、56+2+2/60、source909、两 argv、crypto、证书及 false03 模板全部不变。未新增任何 aux/temp 豁免。RECORDED 精确定义为本次进程观察到 file fsync/close 成功后 os.link 返回成功。当前不调用 directory fsync，目录项崩溃持久性始终未确认，不能称为 crash-durable commit 或 financial receipt；也不存在执行 directory fsync 却忽略其失败的分支。未来若增加 directory fsync，必须另建状态协议覆盖 link 已可见但同步失败，不能借 collector 的语法验证替代确认。复制、崩溃 RPO 和物理 I/O 时限均无新承诺。

首批 157 项 + 原首反例两场景均通过并保留。静态发现双 alias headroom 还需保守预留后，新 source 的第二批 158 项 + 相同两场景均通过，CPU2/10 秒 outer bound，先前 raw 不重标。覆盖原首反例相同注入条件下天然完整私有 prefix、正常发布、close/link 失败、发布后 private alias 清理失败、预算及先前 D1/资源边界。首反例适配只改变 source pin、成功发布/私有 staging 的观察断言，不修改其三项注入或手写 malformed prefix。完整 adapter patch、raw 与源码 hash 单独保存，不执行 SQL/native/owner/crypto/网络/CI。独立组拥有本组件关闭否决权；无 M04/ref/push 或生产资格。

回滚保留首 RED 和本次所有原件，再切回先前固定控制候选；不得把 3e586 的已知缺陷候选重新称为合格实现。source909 与旧/新作业未修改。
