# 新资源协议与 D2：CODE / 设计，全部能力未验证

当前后续阶段：默认关闭的 D2 persistent companion 在固定新 SOURCE `8594a35827b0e064584113de48fda2490cb1c98e` 首次 focused PURE 76 PASS / child0 / exit0，独立 raw 绑定复核尚待闭合；详见 [m0-d2-companion-export.md](m0-d2-companion-export.md)。默认开关仍 false，原 kernel backend 仍 NOT_IMPLEMENTED / NOT_VERIFIED。下文关于“persistent export 尚未实现”的文字是固定3040阶段历史，已被后续 CODE/PURE 状态 supersede，不构成实际 GHA/M06 或生产授权。

最新状态：固定 source `3040d09b576009893c6630f3c19ef4ad35fd774d` / tree `37e3cefe1fd6e318a7094597d6c88ebfe84899b3` 已在root条件预算与独立CODE_ONLY READY后首次运行一次受guard纯batch：**120 unittest条目PASS / 0fail/errors/skips / exit0，CPU2，264,358,860ns，child0**。其中24条新D2/interface测试；静态99个声明方法之外，原RouterAuxContract继承21个ResourceRaceContract方法，因此实际120，不是额外模块或新能力。原stdout为空，stderr19,721字节，合计低于100KiB；外prlimit每文件50KiB，原件保存在 `first-pure-3040d09/`。没有重跑或过滤继承条目。此通过仅是D2与NOT_IMPLEMENTED接口纯正确性，**不是kernel cap实际验证**；physical backend、persistent D2 export、新GHA仍NOT_IMPLEMENTED/NOT_RUN，next_run_permitted=false。

原3040 CODE冻结阶段的历史状态如下，后文“未跑/计划”指该阶段，已被上述pure事实supersede；`policy.json`/`static-provenance.json`原冻结记录不回写，最新状态另见current-status：本分支从固定 C `933c86803020fccbc11949795cb9c75a2262959d` 开始，只写控制 CODE、未来纯测与设计。当时未运行测试或任何能力。至今仍未运行mount、loop、quota、SQL、OpenSSL、业务/native、service、子进程能力、网络或新GHA。原M05 B UNKNOWN/P NOT_RUN、spent05、D1九字段及全部原证据不变；不会给M05补造attempt、elapsed或路径。无生产、容量、HA或真实资金批准。

## 强度与尚缺的证据

| 候选 | 可要求的边界 | 不能据此宣称 |
| --- | --- | --- |
| plain tmpfs size + nr_inodes | 分配页、仍open但已unlink的数据；inode数量上限 | 全部inode/dentry/slab RAM都在192MiB内；disk WAL/FULL持久性；ENOSPC与cgroup OOM等价 |
| 固定总192MiB disk-backed独立FS/images | 卷地址空间内data、journal、inodes、目录/extent metadata和unlinked-open blocks | host backing FS元数据、loop/kernel RAM、进程RAM、provider/source/uploader日志也被该卷限制 |
| 单独host project quota | 该project实际计费的blocks/inodes，须实际验证 | 整个共享FS的journal/global metadata有同样上限；一个inode同时属于case32和normal64两个project |

首选待验证候选是normal64MiB、escrow96MiB、cleanup32MiB的固定独立卷，总地址空间恰192MiB；各卷内部metadata消耗其自身额度，不能额外再加metadata reserve，也不能承诺192MiB payload能填满。原逻辑case32MiB（B/P各自）、normal64、escrow96、cleanup32、total192均保留。case quota需覆盖case tree、root外context-B/P、case-owner日志以及public/case-B/P-safe等所有同case路径；不能只给private/B设project。可研究normal group/UID pool与case project组合，但实现、单位、charging语义和权限尚未验证，CODE不声称已成立。

旧逻辑计量按st_size/high-water字节，卷与quota按其已分配block/inode规则计费；sparse、inline、压缩、去重或共享extent会让两者不同。即使physical cap未来验证，仍不能据此证明原logical case/aggregate字节扫描完整，也不能吞metadata UNKNOWN。手算中的分配量采用明确的独占block配置假设，不是任意FS的实际测量。

tmpfs会改变介质/持久性，原format2拒tmpfs/ramfs的检查保持不动。任何新FS/image也必须有独立storage profile，不能直接与旧625基线同比。原 `collect_host(private)` 和health均读取private FS free并要求MIN_FREE=2,348,810,240B；192MiB卷必不满足。新协议须明确分开真实backing-host free与volume capacity两域，MIN_FREE数值不减，不能把host free偷偷写入旧private字段或静默豁免。当前设计接口默认NOT_IMPLEMENTED/disabled，旧流程完全没有调用它。

## 未来可信边界要求，尚无执行后端

需要root控制的helper创建全新private mount namespace与确切owned mountpoint，pin namespace inode、mount ID、device major/minor、root inode和打开的目录FD；同device不足以识别bind别名。worker使用受控无特权UID/GID，不能持CAP_SYS_ADMIN、chown到其它quota身份或创建/remount新可写mount。source只读，所有其它可写路径/继承FD必须关闭或明确归入上限，包括SQLite temp、TMPDIR、native cache、driver/owner stdout/stderr和safe staged export。仅设置TMPDIR并不能证明覆盖所有写路径。

mount/quota不可用、capability缺失、mount ID/dev/inode/uid变化、未覆盖FD/path、ENOSPC/EDQUOT或I/O异常均fail-closed并保首UNKNOWN，不回退普通目录、不重mount、不延长原clock。physical bound如未来有可信证据，只能另列“卷边界成立”与“辅助metadata UNKNOWN”，不能吞旧missing/main/type/permission错误或把原logical UNKNOWN改成PASS。它不是全OS sandbox，也不约束任意I/O阻塞、CPU、内存或外部provider资源。

导出必须在producer全reaped/closed后，仅允许固定JSON/CMS allowlist，验证len/SHA，再把同一allocation变为只读或提供只读alias给uploader。private namespace的文件默认不可被后续action看到，必须设计可信handoff；直接复制到host会形成额外一份，占用必须仍在原192内获证明，否则NO_GO，不能使用额外2GiB掩盖。upload后只正常umount；EBUSY/身份变化保持teardown UNKNOWN，不lazy/force卸载或删未知路径。证据可信lease与首结果保留。

`kernel_space_design_spec()` 是严格默认关闭的要求描述，`request_kernel_space_backend()` 对任何合法设计也固定拒绝 `kernel_space_backend_not_implemented`。它没有mount命令、sudo假设、quota调用、路径探测或GHA能力宣称。实际后端、future schema/namespace、privileged helper证明、各charging与noescape canary、storage profile及导出卸载验收均未实现/未验证。

## D2 独立 CODE

旧D1所有函数和严格九字段schema、发布路径、cleanup计费与public allowlist不改。D2只有显式 `resource_scan_d2_capture(phase)` 的内存collector；没有旧workflow调用、文件发布、CLI或marker授权接口，默认off。它不影响fresh ContextVar proof token、exact-path/单次消费、parent/main/type检查、最大3scan或50ms原始clock。

新deadline helper使用原门槛那一次monotonic读的elapsed值：`POST_RETRY_SCAN_RETURN / LE / C933_L377` 仍要求elapsed≤50,000,000ns；`QUALIFIED_AUX_ENOENT / LT / C933_L382` 仍要求elapsed<50,000,000ns。attempt为1-based。只有opt-in时额外记录每个scan调用的begin/end wall；其开销照样计入原始started/50ms，不重置预算。scan wall只覆盖scan调用，parent/main资格验证与循环开销在total elapsed内，不能拿两者互换；legacy标签指固定C933的旧行号，不伪称为新文件实际行号。

D2只在deadline失败时记录首capsule：phase、固定scope/aux catalogue、CURRENT或LAST_QUALIFIED_AUX上下文、gate、operator、legacy gate、attempt、实际elapsed、配置deadline和每attempt wall/result。上下文只在本scan当前proof已获认可后派生；last label只是附近已认可aux的上下文，不是导致deadline的DB归因。没有filename、任意路径/路径hash、exception消息、key、nonce或opaque token。其它错误不授予重试、不生成假的deadline证据。

D2验证或collector读写失败只best-effort标UNAVAILABLE，不覆盖原GateError；所有可选读写及状态fallback在保护内。scan的既有BaseException保留，新增起始计时取消不继续scan；成功scan之后计时收到取消也传播。capture/token在正常、异常和nested路径均finally恢复。未来发布D2还需独立kind/严格filename与cleanup32计费，当前不实现，也不往D1中塞字段。

## 手算示例与后续纯测计划

`evidence/designs/m0-kernel-space-d2/state-examples.json` 仅为手算，绝非执行结果。指定示例配置为4KiB块、每非空文件独占至少一块、非inline、无压缩/去重/共享extent，payload分配量指独占已分配data blocks，不是任意st_size。此前提下：unlink-open1MiB路径和为0而卷仍占1MiB；1000个1B文件至少1000个4KiB数据块加metadata；64+96+32MiB独占data blocks再加H>0必超192而早ENOSPC。另一个逻辑示例B32+P32+root normal1=65MiB须被normal64拒。D2示例明确L382在50ms等号失败，L377在50ms等号通过，L377在50ms+1ns失败，且不能从M05 outer9.26秒反推任何scan elapsed。

源码冻结后建议另授一次CPU2、外层10秒、单解释器纯套件：新D2/design 24方法，加原resource_race、entry_types、scan_proof、diagnostics四模块回归。仅新private TMPDIR下原KB级合成文件/monkey stubs，真实child=0；拒绝SQL/UTA import、mount、process/thread启动、网络、信号与native exec，完整first stdout/stderr/exit/source/runtime保存。五模块需要的源码闭包只有controller与五test files，runner守卫另列；不选cold_import、不跑业务/hosted canary。任何首FAIL/ERROR/UNKNOWN不自动重试。该计划本轮NOT_RUN，仍需root另给固定source的具体预算。

可审查的拟命令为 `timeout --signal=KILL 10s taskset -c 2 python3 -I -S RUNNER SOURCE PRIVATE IDENTITY`；RUNNER是本提交的 `evidence/designs/m0-kernel-space-d2/run_zero_child_pure.py`，SOURCE仅物化上述6文件，PRIVATE为新的0700目录，IDENTITY在计量前绑定固定commit/tree、6个SHA及runner SHA。stdout/stderr以0600/O_EXCL预开，outer exit另存。wrapper内嵌的GUARD_CODE逐字节取自独立审核过的C933零额外许可路径，SQL/UTA active import guard另装；所有process/thread/network/signal/raw-fork/native启动均拒绝且记录，绝不启用原six-child allowlist。只对受信已审源码成立，不宣称hostile Python sandbox。该wrapper本轮只写入/AST读取，未执行其guard或测试。
