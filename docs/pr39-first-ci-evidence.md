# PR39 首次 push / PR CI：两轮 FAIL，单job正向证据分列

发布head `5aa7c4e78aaa0b62b73d43fb4f5a8c78d2b648ed` / tree `4e2368513a01b6901be3b32159999e1a373cc8d0`；base PR35 `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`。PR merge `ab6225f8a0b93b212c7c0eb64d3aa8e3a09de422` 的tree相同、parents为base/head，但两个commit不能互相代签资格。两run均attempt1，无rerun。

| event / run | Python3.10 | 3.11 | 3.12 | 3.13 | whole |
| --- | --- | --- | --- | --- | --- |
| push `44238463606` | unit FAIL×1 | success | success | success | failure |
| PR `44238514353` | success | success | success | unit FAIL×1 | failure |

两失败job都在step5 Run unit tests。push job `134580214218` 是 `test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover` 第1461行：`read/stop races exhausted the bounded SH capture attempts`。PR job `134580376988` 同一test但不同断点，第1456行：`bound child did not leave SH after undo within original capture horizon`。这两项分别保留，原因UNDETERMINED；不能按测试名推断已实际验出gate回收通过或失败，也不归为flake或同一根因。原fixture源码相对PR35未变。

两份失败unit各2083run/1FAIL/0ERROR/0skip/worker1，source maps前后相同、unit.txt SHA与summary相符。新增observer四模块的34个实际方法在两份log中分别逐条ok。该局部scope不覆盖whole failure；旧component/typed/pipeline/stdin/actualadapter首结果仍按各source分列，不做相加通关。

失败job首raw log和unit ZIP各只取一次。push ZIP91313B/SHA `8cbfe1c2e57fa5d42b821bc896c60bf551f97a1d18fcac7e9253e0d970eac005`；PR ZIP103243B/SHA `942a778e6903776abe85d073ee07fe51e4d9c63042b6aa8565b8788c8318bd04`。digest/len与provider匹配，各3members首CRC通过；zip、job log、提取的summary/worker/unittest原件全保留，单job所有相关原件分别480183/625494B，保守计入2MiB限额。

root追加授权的成功push Python3.11 job `134580214188` unit bundle亦仅取一次：artifact `14398373453`，101475B/SHA `14540810f18fccbc65c8ac69b1cb5205a8368cc75eaee2d4089f2a9076bb3477`，3CRC通过。其exact C为发布head、2083/0FAIL/0ERROR/0skip/exit0，34新方法均ok。完整runtime是 `3.11.18 (main, Oct 26 2026, 02:48:29) [GCC 15.2.0]` / SQLite `3.46.1`。这只保该CI单job/运行时资格信息；不是whole push、跨版本或local3.12.14合格。

另仅取一个成功push Python3.12 job的小package report：artifact `14399265665`，60244B/SHA `28470236aaa362af3da1ad2ad512ccd12cfc3cc5b8e1fdb61a954bf0751e7c55`，19CRC通过。两个raw JSON的source均exact head；7checks true、installed8/8/isolated，139个changed paths、两observer及两M0 literal均列在required selection，missing/mismatched为空。此为provider报告，未独立下载或检查原wheel/sdist/fullarchive、未本地build，也不改变whole failure。不要把名为uta-wheel-*的约51MB容器误称为wheel文件大小。

## 未来同CI运行时短smoke：仍NOT_RUN

future-ci-smoke-feasibility.json仅记录静态路线。需要另冻结外部control H与launcher/guard；target C必须仍是上述发布head，不能用后来整合证据的branch tip代替。新workflow须root另具体GO，当前没有run/rerun、CI修改、SQL/watch或mount probe授权。

不仅完整sys.version/SQLite必须相等，identity_report还要求QA command_argv[1]等于SOURCE/tools/run_validation.py。原SOURCE为 `/home/runner/work/uta-unified-account/uta-unified-account`，原Python为 `/opt/hostedtoolcache/Python/3.11.18/x64/bin/python`。因此target C要在原GITHUB_WORKSPACE绝对位置、保持clean full checkout；H脚本、QA包与新输出置RUNNER_TEMP外部，H/C分别绑定，不能在嵌套target目录借同tree签名，也不能让H代码混入C的tools/UTA加载。

完整C的Git blob总量208956032B；source256MiB、全新scratch512MiB、private clone子限256MiB与headroom1GiB仍是待launcher落实的预算（source+scratch+headroom1879048192B）。原watch要求kernel RO source/job，只有受控observer/audit输出可写；bwrap/RO不可用就NOT_RUN，不回退RW，不自行改全局权限。逻辑字节预算不证明unlinked-open/FS metadata物理hard quota。只处理全新synthetic checkpoint/router/shard备份，不涉及旧private authority、AuthDB/H1、keys或原10protected PIDs。

即使未来同runtime可运行，60s/15round短profile也不能满足原21600/5400 final gate；只能做真实CLI/SQL/short-cold正例及原strict拒短的反例，不改时钟/coverage窗口。旧16stable+305inflight与4s no-catchup仍独立阻断，financial/6h/capacity批准均false。

## 原件与权限

`evidence/runs/pr39-first-ci/` 首封69个safe原件/投影共2701529B，加seal与说明；private总2771078B，低于64MiB。周期jobs查询实际间隔均≥60s，最小65.069s；时间戳原样保存。四份签名download引用与小package ZIP只留private0700/0600，OWN只有bytes/SHA及两个safe JSON；三个unit ZIP保留原字节。固定PEM/credential/signedURL模式计数0不是安全审计。API JSON按connector返回保存，job logs为connector解码文本，不伪称HTTP wire bytes。

独立只读review待闭合。source policy的NOT_RUN/false是发布前快照，本记录另陈述ordinary CI实际执行，不回写旧标志。默认legacy、UTA=PR35/6010、旧首失败/实际adapter/909/M05证据全部不改；没有collector push、watch/SQL/probe或protected PID操作，production/financial6h/10k/HA/真实资金均false。root负责skip-ci整合及PR正文。
