# router WAL/SHM 精确目录修复候选

M04 first evidence和原8295首RED在4596fe49004171b893a26a850bf4bac6a3fd6414完整保留。实际D1表明首次失败检查对象是PRIVATE_ROOT的AUTH_ROUTER_SHM，errno2，primary resource_missing_non_aux；只能定位本次遗漏的path规则与检查点，不能证明上层目录当时全部稳定，也不能回填旧M02/M03因果。

## 唯一代码行为变化

_sqlite_aux_location的两条现有regex仅将 `shard-[0-9]{4}` 改成 `(?:router|shard-[0-9]{4})`。private_root仍只允许B/P/workload/authority下这些主库名的-wal/-shm，以及原runtime-probe/private；private_case仍只匹配其trusted显式role anchor下workload/authority。实际调用者case_bytes先验证name为B/P，public tree不授予private role。没有basename猜权限、任意.sqlite豁免或新增目录。

同币名main没有sidecar suffix时仍非transient；未知名、其它父目录、public伪私有布局、B/P嵌套借权、symlink、主库或父缺失、Permission/EIO仍拒。遇到精确aux ENOENT才用原nofollow metadata检查parents/main并fresh全重扫。最多3次、同一原50ms，不重置56+2+2/60或任何预算；已见稳定路径/type和regular尺寸下界的原规则保留。

source909 sharding.py实际为authority建立router.sqlite3（149行），与shard-0000/0001及runtime probe共同构成当前入口目录；matching使用相同exchange transaction，没有新matching.sqlite。此变更不引入第二/第三批产品、借贷/清算规则或风险性能优化。

## 原红与新绿不混淆

原8295哈希7a0253…上，tiny fresh fake FS的shard正例PASS，router SHM以resource_missing_non_aux失败，首RED 3,132,600ns、CPU2原件保留。新source另建fake FS运行186项纯suite，0failures/errors/skips，CPU2/1,007,012,485ns；脚本、所有输入SHA及首stdout/stderr在docs/evidence/independent-actions-m0/router-aux-*。这不是actual M04 rerun，也没有读取SQLite、启动owner、crypto、网络或CI。

新正例矩阵覆盖B/P×WAL/SHM×private_root/private_case八组。原严格资源tests也继承应用于router，包括稳定main丢失、类型变化、此前稳定path消失、部分尺寸下界、增长超额、3次churn及50ms不重置。新增EIO、aux/parent symlink、public/错误case、近似但未知名称及50ms相等拒绝。旧D1“router ENOENT仍应拒”是旧policy期望，新版测试改为同一固定label在Permission errno13下仍拒；未改变原首RED输入来凑绿，原测试版本与旧所有raw仍在Git。

## 单列未实现：parent/main身份替换检测

当前stable_types只固定path与S_IFMT，_known_missing_sqlite_aux只验证当前parent为真实directory/main为regular，未比较首次观察的st_dev/st_ino。普通文件或directory被替换成同类型路径仍是已知缺口；本patch没有把它标作解决，也没有执行新的identity反例或把未测假设写成故障事实。

未来独立提案应按显式bootstrap/READY状态，pin授权private root、case/workload/authority各ancestor与已发布main的(dev,ino,type)，在每次fresh重扫和aux复核前后比较，替换一律UNKNOWN而非延长retry或更新pin；尚未发布main不能从启动第一刻强制存在，必须有可审的源目录/生产者状态边界。不得为计量open/close SQLite inode而破坏进程POSIX锁。metadata仍是非原子观测，不能仅凭inode比较宣称防住历史A→B→A或inode重用；应明确writer持有/权限/fencing和故障模型，目录句柄方案也需单独平台验证。

该未来版本必须保持有界对象数、原总deadline与预算，纯交错覆盖same-type替换、父替换、symlink、权限/EIO、失踪main、合法WAL/SHM生命周期及pin重启恢复，之后才讨论单独受限实际验证。不能未经审查把当前type-only假设升级成生产身份保证。

## 审查、启用与回滚

独立组审固定新source的唯一regex差异、source909目录证据、首RED/新setup及所有负控；fake FS通过不证明实际SQLite lifecycle、延迟、容量或HA。M04 spent及其marker/C8295/runtime/public artifacts完全不改；本候选仍使用spent04命名，旧false模板pins未刷新，不能获得新执行权。没有M05/template/ref/marker/push或新负载。M05只可另提计划并由root在独立审后最后GO。

若候选有误，保留首M04和新raw再回滚这两regex；回滚不会重新启用旧spent分支，也不会把M04 UNKNOWN改成PASS。原business source909、四流CMS、所有源/配置/receipt验证及预算原样保留，真实资金与生产资格仍未放行。
