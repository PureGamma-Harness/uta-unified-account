# 909 首次终态封存的独立审查

审查对象固定为 `d243f8c5a12b4a0c8c2f593813b621317a774013`，其唯一父提交为原运行源 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`。本次结论为 **元数据与来源绑定通过，原六小时任务仍为 NO_GO**。这不授予金融验收、生产启用或新任务运行权限。

## 已独立核实的内容

- 原提交仅新增 9 个文档及安全证据文件，`uta` tree 与冻结源一致；manifest 的 7 个载荷逐字节长度和 SHA 全部匹配。
- 独立读取 6 个固定小原件：progress、producer result、cold result、collection errors、final summary、live coverage。每个文件先核普通文件与 1MiB 上限，以 `O_NOFOLLOW|O_NOATIME` 读取，检查前后 device、inode、size、mtime、ctime 一致。其 SHA、大小与首次封存均相同。
- 原生产者确为 `paused`、exit 2，完成 **4,357 / 5,400** 轮，active elapsed **19,443.305304647s**，`final_audit=null`。完整 21,600s 的门槛未通过。
- 唯一资源事件确为 `observer_output_budget_exceeded`、`RESOURCE_NO_GO_OFFICIAL_DRIVER_DRAIN`、`signal_sent=true`。测得 **2,157,259,397B**，超过原 **2,147,483,648B** 预算 **9,775,749B**；范围为 `control_and_observer_except_validated_private_clones`。原记录明确 `financial_corruption_inferred=false`。本审查没有把停止原因归为磁盘最小空闲量或环境重置，也未推断金融腐败。
- 原 cold result 为 exit 1、`ValueError`。冻结 observer 源码的唯一相应消息 literal 位于 704 行，其 SHA 与原 response 的 digest `4a5ed95de5ca7c7837583d12ce1ff661d7aa5b80428619cfa19821d19f1cf37b` 一致；878、894 行错误处理表达式均为 `sha256(str(error).encode()).hexdigest()`。这是静态来源绑定，没有执行 audit 函数。
- 冻结 supervisor 源码的 `final_once` 明确传入 `stdout_limit=LINE_CAP`，且 `LINE_CAP=64*1024**2`。两个前后观察的公开投影均记录 `stdout_complete=true` 与 response 存在。因此把默认 4MiB cap 截断写成原因没有证据支持。
- 原 final summary 的金融资格和总体门槛均为 false，fault schedule 未完成；coverage 为 NO_GO，321 次样本中 16 次稳定 golden、305 次未比较。监督器完成收集不覆盖这些结果。

## 审查范围与证据缺口

本次只执行标准库元数据审查器与 Git 对象读取。首批次 exit 0，外层用时 **164,793,575ns**，审查器自身用时 **85,628,202ns**，stderr 为空。实际执行原件及脚本见 [独立记录](../evidence/reviews/909-first-terminal-independent/first.stdout.json) 和 [执行记录](../evidence/reviews/909-first-terminal-independent/first.execution.json)。

两个约 12.77MB 的前后观察原件没有重新打开；其完整性标志、stable boundary、4,357 轮 golden PASS、`final_reconciliation` 缺失等结论来自已校验 SHA 的首次封存公开投影。因此本次不构成独立账务重算或大响应的第二次逐字段验证。原 receipt 的 MISSING 记录也仅核公开投影，本次没有重新 stat 该路径；原进程身份快照没有再次查询。

未读取 SQL、克隆、timeline、密钥或隔离目录；未执行产品模块、observer、SQL/audit、回放、重启、信号或新长测。原生产者自报 `logs_verified=true` 不能代替独立终态日志校验。已完成轮次的 observer golden 不能代替完整 5,400 轮、成功物理冷重开、完整风险重执行或业务事件回放。资源增长机制及稳定 golden 覆盖不足的具体原因也不由本审查证明。

## 变更与回滚

本 OWN 提交只增加独立文档、审查脚本及其首次输出，不修改原封存的 9 个文件、运行源、预算、配置、schema、服务或任何账务。无数据迁移或兼容性变化。撤销此提交只移除新增审查材料；不得重写原始失败、恢复旧任务、把已耗时折抵新六小时门槛，或将本次审查解释为生产批准。
