# M05 首次实际执行：B UNKNOWN，P NOT_RUN

root 于2026-11-18T01:38:23.128553Z至01:38:25.223472Z完成唯一一次 exact-M push：`cad6e2b8e5efbb13da66376f69ce9dca39e522ba` → `refs/heads/perf/approved-m0-20261117-05`，return0，2.094935027秒。首收据、stdout/stderr及root exact-object GO逐字节保留；只读远端ref随后精确指向该M。05已spent，没有第二次push、dispatch、rerun或补P权限。C `933c868`、M及旧记录均未改；本证据分支从C开始，未引入actual marker。

首次metadata观察即见 once run [44217339075 / attempt1](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44217339075) completed/failure，created01:38:27Z、updated01:38:59Z，job134510349125。manifest/C/workload checkout、runtime setup和pure control test步骤success；实际B/P执行step失败，public allowlist verify与artifact upload success。初始完整run collection JSON、once终态run JSON及connector投影jobs/artifacts均封存，connector投影不冒充完整HTTP原件。另一个general CI首run44217339023从初始collection独立列出，并交独立owner保存后续首结论。

公开result原判型是 `UNKNOWN_OR_NO_GO`。B=`UNKNOWN`，error_code=`whole_case_unknown`；owner outcome=`UNKNOWN`、returncode=-15、leader_reaped=true、stdout_stderr_complete=true，watchdog_reason=`health_or_resource_gate:resource_aux_retry_deadline`。case outer耗时9,269,443,924ns，不是resource scan的单次耗时。P=`NOT_RUN`，reason=`first_case_not_passed`。B的四条closed-stream escrow为PASS、failures空；不代表financial correctness、throughput或B通过。

首artifact14388957599（`independent-m0-safe-44217339075-1`）一次metadata查询后通过GitHub connector一次下载响应获取ZIP，再读取返回的file-service字节，HTTP200；229,224字节，SHA256 `92ab3f0414cfadb11eae10c14d4c6c5896110a6e926a073238b5799cbac620ab` 与provider digest精确一致。ZIP有13个成员，全部CRC正确；manifest列出的12个成员len/SHA精确闭合。9份public JSON逐字节保存，4份CMS ciphertext留在私有原ZIP；本owner未解析CMS、解密、读key或quarantine。signed download response仅保存在0700私有目录/0600文件，公开记录只保存其长度与SHA。root独占后续认证解密，结论须另列，不能用“输出文件存在”当作成功。

## 精确 D1 与可知边界

`resource-diagnostic-CASE_B.json` 原件232字节，SHA256 `28ee44cc688f1b56e0785eacd8e7a16a1fbc788f8d10ec3ab4a38d3ee743a69e`。原9字段为：

| 字段 | 原值 |
| --- | --- |
| kind / version | M0_RESOURCE_DIAGNOSTIC / 1 |
| phase | CASE_B |
| scope | UNKNOWN |
| operation | HEALTH_VALIDATION |
| errno | 0 |
| catalogue_label | UNKNOWN |
| primary_code | resource_aux_retry_deadline |
| unknown_relative_path_sha256 | null |

原schema不含attempt count、deadline、scan elapsed或命中的具体比较位置，全部标为NOT_RECORDED，不能补造。精确C的controller SHA为 `eb447cefe07a04de9dbcf06b370834f4abf3f56a7ef5325313fe44403657d918`：`tools/independent_m0_controller.py:103–104` 固定最大3scan/50,000,000ns；356–357在整个retry前取一次clock；377在retry scan返回后要求elapsed≤50ms，382在已认可ENOENT后要求elapsed<50ms。两处相同primary code，capsule无法区分或给出实际次数。188–195回退UNKNOWN/HEALTH_VALIDATION；171–173对非OSError默认errno0，它不是数据库系统调用errno=0的证明。242–254写D1且保原primary，969与982把owned case失败保为whole_case_unknown，1134在B非PASS时抑制P。

这些是原结果与静态源码定位，不是DB corruption判断，也不支持放宽3scan/50ms、重跑或再次使用05。公开runtime记录实际Python3.12.14/GCC13.3.0、SQLite3.45.1、WAL、synchronous2、replication=false；source-manifest精确909/treecee60b并包含5518文件。control绑定C/M/strict19 marker SHA35cd035d及原预算，四流/public recipient不变。

production、10k/s capacity、HA及真实资金批准均false；next_run_permitted=false。新修复与新的注册只能走另一个版本/另一个ref及root独立审批，不改首证据或spent05。本OWN仅包含safe文档/JSON/text；原ZIP与带signed URL的下载响应保存在私有目录，未上传密钥、DB或明文raw。
