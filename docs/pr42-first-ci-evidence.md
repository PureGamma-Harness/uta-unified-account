# PR42 首次 push / PR CI：八个 job 均 FAIL，原件与安全投影封存

发布 head 为 `f510bf5fea852ca04c87930077861c312320141f`，tree
`f4f4c76c0f946d7ef8a784db1fc4431e86071872`；base 为 PR38 已发布的
`17e0838ff0c153f36ec53a03e4db219e5948ab33`。PR42 保持 Draft。
GitHub API 实际 PR merge 为 `fea8353daf2df005dc1a06f3ee767df2b8c558a0`，
parents 精确为 base/head，tree 与 head 相同。push run `44255323419` 与
PR run `44255350395` 均为 attempt1，最终 completed/failure；八个 Python
job 均在 step5 `Run unit tests` 失败。collector 未重跑 CI、测试或服务。

| 事件 / run | Python | job | tests | FAIL | ERROR | skip |
| --- | --- | --- | --- | --- | --- | --- |
| push44255323419 | 3.10 | 134635530818 | 2102 | 0 | 25 | 0 |
| push44255323419 | 3.11 | 134635530462 | 2102 | 0 | 25 | 0 |
| push44255323419 | 3.12 | 134635530799 | 2102 | 0 | 25 | 0 |
| push44255323419 | 3.13 | 134635530823 | 2102 | 1 | 25 | 0 |
| PR44255350395 | 3.10 | 134635623205 | 2102 | 0 | 25 | 0 |
| PR44255350395 | 3.11 | 134635623502 | 2102 | 0 | 25 | 0 |
| PR44255350395 | 3.12 | 134635623741 | 2102 | 0 | 25 | 0 |
| PR44255350395 | 3.13 | 134635623514 | 2102 | 0 | 25 | 0 |

每个 job 的25个 ERROR 对应同一组25个唯一测试 ID，但每次原始标题、
traceback 与消息摘要均按 job 单独保存。最终异常都是
`uta.credit_artifact.CreditArtifactError: unsupported loaded financial constant type`。
典型实际栈是 `tests/test_credit_artifact.py:119` 的
`before = credit_code_artifact()` → `uta/credit_artifact.py:244`
`_loaded_modules(_MODULES)` → line215 `_hash(_static(value))` → line142
原始拒绝分支。该分支源码的 code literal 为 `credit_artifact_unavailable`；
这不是 collector 从异常对象提取到的 runtime code 字段。
具体 unsupported attribute 没有出现在原始 traceback 中，记为
`NOT_OBSERVED`。共同异常或共同 raise 不证明所有 case 的完整根因相同。

| ERROR 所属测试模块 | 每 job 唯一 ID 数 |
| --- | --- |
| test_credit_artifact | 11 |
| test_credit_audit_v2_schema | 1 |
| test_credit_v2_code_binding | 1 |
| test_credit_v2_legacy_and_lease_runtime | 2 |
| test_credit_v2_native_history_boundary | 2 |
| test_credit_v2_native_late_boundaries | 2 |
| test_credit_v2_process_restart | 1 |
| test_credit_v2_realtime_clock | 1 |
| test_credit_v2_runtime_chain | 4 |

push3.13 额外唯一 FAIL 是
`test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`。
原 `tests/test_durable_faults.py:1456` 为
`self.fail("bound child did not leave SH after undo within original capture horizon")`，
最终为 `AssertionError`。这是行情发布共享锁恢复测试的实际失败；collector
没有复现任何 SIGSTOP、PID、worker 或锁操作，也不推断其与上述 ERROR 同因。
该测试源码与 PR38 base 相同。所有 footer case 的相对路径、精确行、Git blob
与 SHA256、原显示行和 base 比对见 `failure-classification.json`。
成功 case 输出中的预期 child traceback 不计入测试 ERROR/FAIL。

八份实际 worker JSON 均精确9keys，`lease_observations` 为原生空 list，
`lease_observations_truncated` 为原生 bool False；summary 的这对保留字段完整、
同类型且相等。原7个 worker 字段与 summary 也逐类型和值一致。
这是实际 producer/report 形状的观察，不是资格通过：八份
`unittest_passed`/`passed` 均 false、worker exit1、errors25，原资格门槛仍应拒绝。
collector 未调用资格函数、未把先前6×32内存 PASS 当成完整 CI 通过。

八个失败 unit artifact 各只取一次，均小于104KiB，provider length/digest
与实际 ZIP 字节匹配，24个成员首读取 CRC 均通过。每份只有原始
summary、worker-result 与 unittest 三个成员，账面 test_log SHA 与原成员相同。
push 的实际 code_commit 为 head，PR 的为上述实际 merge；全部八份 source
before/after maps 相同，368个相关 Git blob 的 SHA256 与精确 head tree 字节
一致。PR 使用 head 字节核对的依据是 API 已证明两者 tree 相同，而非虚构的
本地 merge checkout。详见 `artifact-verification.json` 与 `source-pins.json`。

完整首次 connector 原件、原 decoded job logs、下载引用与 ZIP 均先封在私有
0700目录、0600文件。所有 unit 成员经过逐文件检查：凭据、私钥、实际控制值、
UUID/32hex、header 与签名 URL 的六类有界模式匹配均为0；全部最终 footer
异常消息与已审源码常量一致。公开 unit ZIP 和三个成员保持原字节。
这是有界检查与源上下文核对，不是安全审计。八个 job log 每份均包含
认证/header 配置日志，原完整 decoded 文本继续留私有；公开 `.safe.log`
仅为明确标注的逐行删除投影，各 receipt 绑定原字节数/SHA和删除行号。
它们不冒充完整原 log。connector 未提供原 HTTP wire bytes/response headers，
因此不对其作 hash 或完整性声称。签名下载引用、headers、DB 与 key 不公开。
五份 SAFE log 保留了原非敏感行中的30处尾空白。首次格式检查非零，原输出
保存在私有目录；没有为格式检查改写任何字节。仅对这五个按 seal hash 固定的
精确路径作格式检查排除后，其余新增文件检查通过，见
`whitespace-validation.json`。这不是对原 CI 或业务测试的重跑。

实际 archive bytes 总计786919B；全部 decoded log 和私有派生副本仍低于
64MiB总预算，每 ZIP/decoded log 均低于2MiB。未取任何成功 unit、成功 package、
wheel 或 sdist：本轮没有成功 job，build/package/installed 实际验证步骤均在
unit 失败后 skipped，没有可用的成功小 package 报告可取。
always-upload 运行不代表 package 验证成功。

首次查询与采样区间完整保留在 `observations-index.json`；记录的是 clock tool
观测区间，不把稍后的文件写入时间伪作采样时间，也不声称固定30秒 cadence。
两轮 terminal 后停止 polling，没有 redownload、rerun、workflow 修改或额外 CI。
本新增 SAFE 交付只含 evidence/docs，由 root 另组独立 RAW 审查后再整合；
本封存时独立结论为 PENDING，后续应单列 closure，不能改写首原件。

PR38 原首 FAIL、baseline 的3个 conditional RED、88da 首12方法的
11OK/1FAIL/45entered、隔离 m08 的1×4 PASS、strictcompat 的6×32 limited
pure PASS 都保持各自 source/scope。当前 whole push/PR 仍 FAIL，未解决的
case 保持 UNDETERMINED，不推断真实财损。Phase2、生产、真实资金、HA 与
10k/s 均 false。回滚本次 evidence-only提交不改变发布 source、金融数据或
历史命令；所有私有原件与失败记录必须保留，不得清理后重跑改绿。
