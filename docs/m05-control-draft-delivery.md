# 控制面 Draft 候选：安全 C933 + 两个 public provenance include

拟交付分支为 `delivery/m05-control-package-fix`，base为PR25的 `delivery/spawn-registration-recovery`，已只读确认其head精确为6010。本分支继承安全C933与M05首实际执行safe OWN，generalCI首OWN `8c8e068`（其soleparent为安全C933）仅以docs/evidence cherry为9e52ec1。actual M05 Mcad6与actual M04 e643均不是祖先；tree及909以来历史均无actual `config/independent-m0-approved.json`。uta tree保持6010的 `4a0d5a989f0d7112454e41bbdb0162ffef34dbe4`，无业务runtime差异。

唯一新增package CODE SOURCE为 `9cd87f7d0fbacdfd87a58dbef6ca24713dc3fe95` / tree `857fcc5e3c349a11b4fd8c1e007dfe0a2640e32d`。相对其parent，唯一变化是MANIFEST两条literal include：

```
include evidence/independent-m0-entry-type-provenance/pure-once01/inputs.sha256
include evidence/independent-m0-scan-proof/pure-once01/inputs.sha256
```

MANIFEST SHA256为 `5481cbc4ef214bd62f5dbf32e3de24eecbcf083512762988da27c7ef3f7fe909`。两选中Git blob分别423B / SHA `ce4aec6aca4bdf07cf3db94efb188ee1db8bef74737621b809f0f9dbf3f75f0e`，207B / SHA `e78d50fcfe4569792b1b32de871b98f19923a73c5330e92dc605ebdb19cfdf36`，逐字节等C933原件，仅含tools/tests相对公开源码provenance。没有新增glob，也不回写这些历史input hash为当前controller证明。

触发问题来自M05 exact-M首次general CI run44217339023 / attempt1：四实际runtime3.10.22、3.11.18、3.12.16、3.13.18各2049 unit PASS，前置compile/demo/replay/acceptance/formal/wheel步骤success，但step19 verifier的7项check中只有sdist_required_files_exact=false，missing恰为这两path。后续installed validation与review artifact步骤均SKIP。四份完整decoded原日志8,947,812字节、原API/summary已保留；旧FAIL/skip不改。新增literal静态上选择这两个既有Git blob，**新SOURCE的实际sdist/wheel/installed/CI尚NOT_RUN**。

独立只读CODE审确认两literal和原缺失因果、source/hash/typed路径、无actual-marker祖链、runtime零diff；没有build/test/import/SQL/native或网络执行。静态reader只读取Git/文本，exit0不是build验收；源码/patch/stdout/stderr/exit/seal和独立结论在 `evidence/preparations/m05-control-draft/`。

M05实际首结果继续为B UNKNOWN、P NOT_RUN，D1仅记录resource_aux_retry_deadline且scope/label未知；原4e ERROR、G stub、d58 guarded PURE、actual M05 first均保留原source含义。root首次四流CMS认证/绑定PASS但流为空，不能由此推断driver从未启动、数据库损坏或资金损益。05已spent，所有production/capacity/HA/真实资金及next_run flags继续false。

## 提交、部署和回滚边界

本次只准备可审的Draft PR标题/正文与冻结source，root审核前不push/开PR；PR号由实际创建决定，不预占35。拟base为PR25/6010，不能向perf登记分支提PR。root后续若批准普通delivery分支push和Draft创建，其新source GHA/package/installed结果必须另封为新结果，不能替换44217339023首FAIL，也不能称重跑原CI。

交付前置是新source完整archive与installed验证通过并独立复核；当前没有运行这些验证。合并此Draft不部署服务、不改schema，不恢复M05或放宽3scan/50ms、原B/P预算、host/free/byte/CMS gates。package回滚只撤销这两条MANIFEST include，控制面整体回滚回PR25/6010安全基线；保留全部首证据。未来实际诊断须新版本/新ref、fresh登记与root另行审批，不能再push或重建05。
