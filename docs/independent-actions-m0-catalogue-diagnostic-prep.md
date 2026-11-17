# M03后续最小PREP：实际文件目录与安全首失败诊断

本页是source-bound方案，**没有实现新的豁免、没有04登记或负载授权**。M03原B UNKNOWN/1.811秒、P NOT_RUN、escrow仅3of4，以及缺失具体path的证据缺口保持不变。首安全OWN598f671保原公开JSON与root三条空流认证观察，不能根据此静态清单推定M03是哪一个文件消失。精确源/控制Git blob、SHA、代码位置与字段合同见 `docs/evidence/independent-actions-m0/m03-source-catalogue-diagnostic-proposal.json`。

## 从实际入口得到目录，不能只重复前次shard例子

固定argv仍是 `run_managed_benchmark.py`、2shards；run()第586行将workload/authority交给DurableProcessRouter，后者使用ShardRouter。

| 文件类别 | 固定M0实际路径（以private root为基准） | source909事实 | 本轮动作 |
| --- | --- | --- | --- |
| 控制库 | B/P/workload/authority/router.sqlite3 | sharding.py:149 | 纳入静态目录，未授权新豁免 |
| 两个账户分片库 | B/P/workload/authority/shard-0000.sqlite3、shard-0001.sqlite3 | sharding.py:180、212；argv shards=2 | 当前逻辑按四位数字识别，未来目录应绑定实际0/1，非任意分片 |
| WAL/FULL探针库 | runtime-probe/private.sqlite3 | 原控制器runtime_probe代码 | 纳入静态目录，规则未改 |
| matching | 使用同一exchange._transaction()，不增加新DB名 | matching.py:38–50；sharding.py:582 | 不虚构matching.sqlite3 |
| 另一撮合清算benchmark | 另一入口下shard-{index}.sqlite3 | run_matched_liquidation.py:118–126 | 当前M0未调用，不能借此放宽路径 |

每个实际main可能有`-wal/-shm`，因此本入口应评估3个case main加1个probe main的8种sidecar，而非仅此前碰到的shard SHM。router aux当前未获新豁免。这是完整性差距和未来审查对象，不是M03因果结论。main在bootstrap可能尚未发布，不能从一开始要求全存在；一旦发布/READY，稳定main必须继续nofollow验证，不得以sidecar生命周期掩盖main丢失。

source909 storage.py:36–53还明确用`.uta-create-` mkstemp→0600/fsync/close→hardlink main（不覆盖）→finally unlink创建DB。只有精确DB父目录和声明的初始化阶段有此源依据；不得把任意`.tmp`、任意basename或不同benchmark借入当前权限。metadata检查不得为了资源计量raw-open/close SQLite inode，避免破坏同进程POSIX锁。

## 先让下一次未知可辨识

最小建议先新增独立的资源首失败安全record，不改变重试许可或资金判断。它由parent controller在冻结owner把错误压成string之前写入；原case-owner/driver stdout/stderr不追加、不改写，也不把诊断record冒作第五条流或补齐缺失第四条。

允许字段为固定version、scope/phase枚举、operation枚举、exact int errno、catalogue label和unknown path SHA256。scope由显式已审调用点给PRIVATE_ROOT/PRIVATE_CASE/PUBLIC_ROOT等，不从目录名推断。operation区分ROOT_LSTAT、ENUMERATE_DIRECTORY、ENTRY_LSTAT、VALIDATE_PARENT、VALIDATE_MAIN、RETRY_STABLE_SET、RESOURCE_LIMIT。label来自静态固定目录，未知只记录role-domain-separated relative-path SHA256；历史M03未保路径，必须标unavailable，不能回填猜测hash。errno是filesystem errno，不与SQLite错误码混用。

严禁任意exception str/repr、absolute path、basename/随机suffix、headers/key/nonce/request或可扩展自由文本字段。schema精确key/type/长度验证，bool不是int；含敏感sentinel的unknown路径只可影响hash，不能出现在序列化结果。first-per-phase采用固定安全文件名、nofollow/O_EXCL、最多4096字节、fsync，直接写不再新建会rename的观察器临时文件；从既有cleanup32MiB中预留，不增预算。写失败仍UNKNOWN并只给固定diagnostic-unavailable标记，不伪造成功，也不能为诊断跳过资源门槛。

新record只作额外安全artifact JSON，phase可区分CASE_B和ESCROW_B。这样下次能够区分哪个scope/operation/class首先失败；当前M03两个typed错误没有这份记录，无法由相同字符串证明同根。

## 留存worker同样要建模发布过程

原m0_stream_escrow.py:300–307将固定checkpoint`.json.part` fsync后os.replace为final JSON；309–319先journal完整cipher再从private staged rename至public exact path。原controller还将case safe-staged目录原子移至public。它们都有源依据，**但没有证据证明本次M03就是其中任一项**。

不能直接忽略这些ENOENT或给escrow关闭health gate。需要在行为变更前评审其“同一逻辑对象跨private/public位置”的有限状态与保守计量：完成字节/hash/协议已由owner确认、每次transition有固定目的地、只允许已审生产者/角色、活文件和partial字节均计量；重扫保留已观察稳定main/type与尺寸下界。无法证明目标或状态时仍UNKNOWN。checkpoint临时文件、DB发布临时文件和cipher发布不是同一类，不能共用宽白名单。

## 可独立否决的下一实施顺序

1. 单独实现安全schema/首record，纯stub注入scope/operation/errno/catalogue/unknown含key-nonce的路径，证明无泄露、重复只保首条、诊断写失败不放行；资金/四流/预算行为不变。
2. 独立审实际四main/8aux目录、bootstrap/READY状态和显式role；若批准再做精确router aux等行为修复，未知/其它benchmark/private-public借权仍拒。
3. 对create/checkpoint/cipher/directory publication做有界交错模型与pure文件metadata canary；证明增长/稳定main丢失/权限/EIO/symlink/重复发布都不会被fresh扫描隐藏。原3次/50ms、56+2+2/60与escrow20+2+2及64/96/32/192MiB约束不变。
4. 只有以上固定代码和独立组件通过、root另行授权后，才讨论全新的低量R&D尝试。当前无04、native、SQL、CI、crypto执行GO；不rerun旧M03，不补P，不改所有首FAIL/UNKNOWN。

这些工作不解除PR22恢复错误、旧24h提前退出、三次M0未完成的门槛。生产、万笔30分钟、HA、可靠性一律NO_GO。
