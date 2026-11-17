# D1：不改变资源准入的安全首失败诊断

本候选只增加诊断控制面。基线是 ab933bec61d5c4be3e40c1a337f8ce55705ba48d；金融源码仍是 909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0。M03 原 B UNKNOWN、P NOT_RUN、仅三条 available cipher 的事实保持不变；其具体 missing path 没有记录，根因尚未定位。本次纯文件/假对象测试不能补回该证据。

## 事件发生点与覆盖边界

parent 的既有 health callback 按当前阶段写首条事件：CRYPTO_CAPABILITY、RUNTIME_PROBE、CASE_B/P、ESCROW_B/P。escrow_closed_case 在创建留存 owner 前的原 resource_usage 也进入 ESCROW_B/P 的诊断包装。PREFLIGHT 和 FINAL_PUBLIC_VERIFY 只是 schema 保留值，目前没有新增对应调用点。child case_pipeline/case_worker 和其终态资源检查保持原字节逻辑；D1 v1 不承诺覆盖 child 独立失败、final source replay、provider 故障或所有任意异常。

事件来自相同 metadata 检查抛出的异常，在其被 owner 转为安全字符串以前注记。原资源条件不变，成功重扫不生成失败事件。label 仅用于解释，例如 router SHM 可以获得 AUTH_ROUTER_SHM，但当前仍按原 resource_missing_non_aux 拒绝。新目录、router aux、create/publish 临时文件均未获得豁免。

## 精确公开格式

每份 JSON 恰好九个字段，未列字段全部拒绝：kind 固定 M0_RESOURCE_DIAGNOSTIC；version 为 exact int 1；phase、scope、operation、catalogue_label、primary_code 是固定枚举；errno 为 exact int 0..4095；unknown_relative_path_sha256 为 null 或 64 位小写十六进制。bool、NaN、Inf、浮点 errno、重复 JSON key、自由文本和嵌套同名记录均不接受。完整枚举及源指纹见 [d1-contract.json](evidence/independent-actions-m0/d1-contract.json)。

scope 来自显式扫描上下文，绝不据 B/P basename 授权。已知目录映射到固定 label，不公开原路径；UNKNOWN 路径仅输出 SHA256(role + NUL + filesystem-encoded relative path)。若路径不属于两个已知 root，只哈希 UNKNOWN 域及原 filename 的字节，不公开这些字节。无可用路径时 hash 为 null。hash 是可关联标识，不能声称匿名化或证明文件存在。errno 是操作系统 errno，0 表示无可用 errno，不映射 SQLite 状态码。

禁止 arbitrary str/repr、绝对/相对原路径、basename、随机后缀、request、header、key、nonce 和原始流内容。公开 primary_code 仅接受固定 GateError code，权限和其它 OSError 映射到固定类别，其余异常统一 UNCLASSIFIED_RESOURCE_ERROR。原异常对象及 cause/context 在私有控制流保持；不会将任意异常文本复制进 D1。

## 首条保存、失败与预算

每阶段固定文件名 resource-diagnostic-PHASE.json，owner-only 目录中 O_EXCL/O_NOFOLLOW 创建 0600 文件，先严格验证 schema，序列化不超过 4096 bytes，flush/fsync 后才返回 RECORDED。同阶段不覆盖首条，返回 ALREADY_RECORDED；无法记录返回 UNAVAILABLE，原错误仍为 primary，运行仍 UNKNOWN。fsync/write 失败尽力把仅本次可选 prefix 隔离到 private 的 resource-diagnostic-incomplete-PHASE.json；隔离失败尽力删除该 prefix，绝不修改 driver/case-owner 四条原流。

可选记录收集失败不会替换已确定的 primary。坏记录不加入 manifest，UNAVAILABLE 显式保留；剩余 malformed/unlisted public 文件仍使原 public allowlist 拒绝。存储不可写、权限/EIO、进程骤停时不承诺诊断持久送达、跨机 RPO 或完整 artifact。

D1 文件和隔离 prefix 使用既有 cleanup 32 MiB；normal 64 MiB、escrow 96 MiB、total 192 MiB、MIN_FREE 2348810240 bytes 均不增加。写前有限已知 cleanup slot 的 lstat 计量不是原子快照；后续完整 resource_usage 同样计入新文件。未知 cleanup 文件仍不获新许可。这不是 OS quota，也不对 I/O 或崩溃行为给出新承诺。3 次/50 ms 原重扫时钟和 56+2+2/60 秒 case owner deadline 不变。

## 验证、启用与回滚

首 14 项 D1 测试、149/153 项中间 suite 原 stdout/stderr 和 first source snapshot 全保留。封版 154 项（其中 D1 19 项）全部通过，固定 CPU2，10 秒 outer timeout；实际单调耗时 874383323ns。纯 metadata/fake 验证的审计钩子未收到 subprocess、SQL 或网络执行事件，也未导入产品/SQLite 模块；未执行 native 或真实 crypto。最终 source-bound 观察和 AST 不变量另存原件。负控覆盖 primary/cause 保留、敏感 sentinel、权限、fsync、隔离/删除双失败、cleanup 满、首次不覆盖、public 借 private label、未知 schema/嵌套文件及四流字节不变。

两个 workflow 仅把新增纯测试文件纳入控制 checkout；checkout source、预算、argv、recipient 和 crypto bytes 不变。现 false03 模板故意不更新，旧 control pin 不具备新候选执行资格；不创建 M04、触发分支、marker 或新负载。独立审固定候选以后才可讨论后续提案，当前生产、容量、HA、可靠性均未放行。回滚是保留新首证据并切回 ab933 控制候选；不删除旧首失败，不动 source909 或在运行作业。
