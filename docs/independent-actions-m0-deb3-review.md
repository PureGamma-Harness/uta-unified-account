# deb3fc5 独立关闭复核：原八项已关闭，新增四项仍否决

**结论：NO_GO。** 固定 C 为 `deb3fc56ec249c78833b786b45a2f708fea57dd5`，controller SHA-256 为 `bed27815344703a3180ebf08214157470d0495226571121f85c39aeb62dd455f`，once workflow SHA-256 为 `fc96454a1407ed137edd0b8e522dae2c5e58ea6beca2a6358fa142026ef8c32d`。原 e444/07a90741 否决、首RED和review helper首cwd错误均保留；没有将旧结果改记为通过。

本次仅用固定 Git/AST、合成文件与纯 stub。两个 helper 读取不可变 Git blobs 后禁止controller的 subprocess入口，均未导入 `uta`/`sqlite3`，未运行SQL、真实driver/owner、profile、Actions、dispatch、push或实际M/登记。没有读取私钥或执行CMS；下一crypto实现不在本C资格中。

## 原八项实际关闭

从不可变07a90741取原 helper，保留原 e444 literal shape fixture和八个变异，仅适配C/hash pin，并让第八项经过新增的真实 `verify_population`。逐行适配patch保留于 `adapter-vs-original.patch`，未改变原始反例数值。

首次复核在CPU3、`19:21:25.995312–19:21:26.084340 UTC` 完成，89,026,478ns：两个一致性正例接受，八个原反例分别以 `summary_outcome_counts_disagree`、`negative_numeric`、`financial_rate_identity`、`quantile_order`、`receipt_original_cid`、`receipt_outcome_identity`、`latency_time_identity`、`cross_file_outcomes` 拒绝，exit0。第八项的两个单文件分别自洽，必须通过跨文件join拒绝，不能要求单文件parser单独判断未知的另一总体。

## 新增receipt真实分类缺口

源909 `benchmarks/run_managed_benchmark.py:134–143` 的 `terminal_outcome` 对REJECTED解析 `receipt.error`（字符串则JSON解码），按 `error.status < 500` 记业务拒绝，否则记控制/行情拒绝。deb3只检查REJECTED状态，没有校验该分类依据。

独立新fixture在原200行160/20/20总体上仅补正常源形状的error字段：SUCCEEDED为None，业务拒绝status400，控制拒绝status503。该正例通过；随后只改一行receipt.error，其余summary、CID、state、时间戳和200行总体都不变。以下四项经 `project_summary → project_arrivals → verify_population` 仍被接受：

| 合成变异 | 与源909分类的矛盾 |
| --- | --- |
| business标签携带status503 | 应为控制/行情拒绝 |
| control标签携带status400 | 应为业务拒绝 |
| REJECTED.error为非JSON字符串 | 分类无法解析，应UNKNOWN/拒绝 |
| REJECTED.error缺status | 分类依据缺失，应UNKNOWN/拒绝 |

首边界运行于CPU3、`19:25:35.938619–19:25:36.228943 UTC`，292,812,028ns，exit1。四项首RED完整保存在 `boundaries-first.stdout.json`，未覆盖；controller原生过程入口零调用。这里不是声称真实source909已经生成矛盾回执，而是证明当前接纳层能接受与其真实分类规则冲突的输入。

应在新revision核验REJECTED.error的可解析形状、status类型与业务/控制分类，并保留安全的分类依据；不能把未知或畸形error重新归一成业务拒绝。严格新契约将拒绝此前省略error的partial正例，因此后续fixture可仅补源909的正常error字段，同时保持原八个变异及旧历史结果不变。作者已收到首RED，review未代修其文件。

## 边界已证实的纯控制范围

同一次边界运行还实际通过以下控制：禁止bulk `gzip.decompress`仍可处理正常200行；65,537字节单行在JSON解码前拒绝；累计超过8MiB逐步拒绝。新代码的每次readline取min(65,537,remaining+1)，避免原先先全量展开的问题。这里没有做OOM或真实内存压力试验。

独立fake owner检查了56秒watchdog、2秒grace、2秒kill参数，确认source hash、完整parser、输出hash/fsync都发生在受监管case pipeline内；hash、parser、最后fsync UNKNOWN均停止并保留私有首字节；模拟父收集超过60秒时，已发布安全目录移回私有quarantine，不能进入公开manifest。五项纯控制全部通过，**不证明真实PID清理或物理60秒硬实时行为**。

静态新增case-worker descriptor限制UID0600、父PID/birth及存活、C/source/hash、boot/host、新session和单CPU。driver `start_new_session=False`，由外层source909 frozen pidfd/session owner覆盖后代；原工作负载argv不变。case级重做source核验，driver、parser、profile语义、hash/fsync和staged publication均在独立worker内。父descriptor准备/收集再按完整60秒门槛拒绝超时，不能将不可中断I/O或调度延迟说成已验证的物理上界。全局源预检、host/WAL探针及最终upload仍属于6分钟job范围。

## 资格与保留边界

deb3仍只有投影和runner生命周期内的私有原stream，不能承接完整raw持久交付。root已决定下一独立commit采用仅stdout/stderr的CMS AuthEnvelopedData AES256GCM escrow，但本次未评估或执行该实现；不得根据本轮parser部分关闭提前登记M或执行远端M0。

新C须关闭四个新增分类反例、保留原八项关闭与新gzip/owner控制，再对后续crypto设计/纯fixture独立验收并重新固定最终C。source909、old24、firstsmoke和本机cohost预算均未改变。M0仍是R&D，不是万笔容量、清算成交、HA或生产资格。

本提交只新增review证据、脚本和说明，无运行时/API/数据库迁移或部署。回滚为撤销review提交，首RED、旧C、原工作负载和原实验须保留。输入和结果摘要见 `review-manifest.json`。
