# PR35 新源码首 CI：push 四绿，PR 3.11 首 unit FAIL

固定head `f6ef89b213ac76813ad31687aa4ff825d9d72585` 的首push run [44220585793 / attempt1](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44220585793) completed/success；首PR run [44220725630 / attempt1](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44220725630) completed/failure。push实际checkout为head；PR实际checkout为merge commit `e71b6e1ac6dc0b0c7fa60bfbfb49822d12328eea`，其parents为6010/head，tree `3066c5be3352fb73c8382aedfa153440bfc30cb8` 与head完全一致。原API/merge object/首次观测及终态投影均保存，没有rerun或修改spent05。

| event / runtime | unit 首结果 | 真实 sdist/wheel 七检查 | 真实 installed 八测试 |
| --- | --- | --- | --- |
| push / 3.10.22 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| push / 3.11.18 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| push / 3.12.16 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| push / 3.13.18 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| PR / 3.10.22 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| PR / 3.11.18 | 2049 run / 1 FAIL / 0 ERROR / 0 SKIP | SKIPPED | SKIPPED |
| PR / 3.12.16 | 2049 PASS | 7/7 PASS | 8/8 PASS |
| PR / 3.13.18 | 2049 PASS | 7/7 PASS | 8/8 PASS |

实际SQLite均3.46.1，Python build/GCC/platform/affinity/checkout与各unit worker exit、source unchanged/clean字段均来自对应完整首job log。七个成功job的step19、step20、review artifact步骤均真实success，日志分别含七检查true/missing空及installed 8 tests零fail/error/skip；不是只依据整job绿灯。PR3.11之后所有compile/package/installed/review步骤跳过，不能把push结果转移给这个失败job。

## 首 PR3.11 失败与一次 unit ZIP

job134521592140唯一FAIL为 `test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`，`tests/test_durable_faults.py:1525`。原断言：`AssertionError: [] is not true : original bound PID did not exit within the unchanged five-second recovery horizon`。完整unit summary/worker-result/unittest与唯一failure tail保存；code_commit=PR merge，source unchanged和前后clean均true。这里不判定回归因果或将其称为偶发通过；没有重跑、signal、本地SQL/native或改五秒门限。

仅这份实际失败unit ZIP14390248168下载一次，100,552B，SHA256 `b794893209f186ad6b08904c3b809eed30fc5c55893d3be48d346cb2ab417305`，HTTP200/provider digest/ZIP CRC精确闭合。成功unit ZIP未下载。

## 明确一次成功完整包审核范围

选择push Python3.12的review artifact14390317989（49,228,377B，SHA256 `1d0d1da1fc416a371884f71563bf6f4f27803c93b9bbb7176b805d18ed455d94`）及其validation companion14390168340（58,225B，SHA256 `0c5ac33f9b29ff96e0aa09a23c2549889b229227d9aab508d98735e3897021ef`），各一次下载，HTTP200/provider digest/CRC均真。原ZIP及两个nested wheel/sdist仅留0700私有目录/0600文件；signed download response只在私有文件，公开OWN仅长度/SHA绑定。其余六个成功job由各自完整首日志的实际七检查与installed结果证明，不宣称对所有package二进制逐一下载审核。

`audit_selected_package.py`只做Git/AST/TOML/ZIP/TAR/JSON读取，不build、install、import uta或执行SQL/native。它独立重算七检查：version、wheel_runtime_exact、sdist_runtime_exact、sdist_required_files_exact、legacy_fixture_pinned、legacy_fixture_licensed、entry_points，全部true并逐项等CI report。sdist完整6,794条tracked Git blob均presence/内容OID匹配，流式读取191,415,518B；wheel/sdist runtime SHA、声明version0.5.0a1、三entry points及legacy fixture pin/license均闭合。两新增public inputs.sha256成员实际存在、SHA正确。companion的artifact SHA/len、installed runtime digest、8 tests零fail/error/skip、isolated=true/PYTHONPATH=null及所有记录的installed CLI exit0均交叉核真。

8份首job logs保留connector提供的UTF-8字节，CR不存在、末尾LF不变；不是HTTP log archive原字节的声明。API collection与run/merge JSON保留原content字符串；jobs/artifact connector投影明确标识。所有下载响应和ZIP均一次，不重试。source/head/actual merge/source-tree、每job summary、每ZIP/member CRC/hash、audit首stdout/stderr/exit及safe seal均在 `evidence/pr35-first-ci/`。

观测限制如实保留：首次run collection观察为02:06:29.956Z，两次pending jobs采样为02:08:08Z和02:09:41Z，首次terminal jobs采样为02:16:56Z；中间有较长采样空档，未伪称持续30–60秒间隔。provider终态updated_at分别为push02:12:54Z、PR02:14:30Z，精确步骤时间以原log/provider为准。

本新source证明两literal include的sdist缺失在成功job已关闭，旧M05/general CI的首FAIL/UNKNOWN不被替换。PR35仍有首unit FAIL，不能称整体绿；M05 B UNKNOWN/P NOT_RUN、05spent不变。production、10k/s capacity、HA、真实资金及next_run批准全false。此OWN只含safe证据，不改runtime、source PR head或任何登记ref，由root另行[skipci]整合。
