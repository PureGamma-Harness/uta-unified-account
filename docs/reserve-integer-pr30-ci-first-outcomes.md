# PR30 首次 CI 独立验收

本次结论：**未通过 CI 验收，未批准生产**。PR30 的 push 和 pull_request 首次运行均在 Python 3.13 的 `Run unit tests` 步骤失败。两个运行各执行 1835 项测试，均为 1 failure、0 errors、0 skipped，退出码为 1。六个其余 whole-job 的 success 结论不能替代这两项失败。

验收负责人：Codex 子代理 `/root/pr30_ci_first_outcomes`；源码范围另由子代理 `/root/pr30_ci_first_outcomes/source_binding` 独立只读核对。此次没有执行测试、重跑 CI、改变工作流或启动业务进程。

## 首次运行与源码绑定

仓库：[PureGamma-Harness/uta-unified-account](https://github.com/PureGamma-Harness/uta-unified-account)，[PR30](https://github.com/PureGamma-Harness/uta-unified-account/pull/30)。

| 项目 | push | pull_request |
| --- | --- | --- |
| Run | [44201524202](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44201524202) | [44202048314](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44202048314) |
| Attempt | 1 | 1 |
| Python 3.13 失败 job | 134456555145 | 134458366604 |
| 实际 checkout / summary code_commit | `b5a68dc29122d5b07a2dccc0500125b48a902a96` | `47302fc4250ac14adac51ab7a4ac7307d13d8f71` |
| summary duration_seconds | 420.908896442 | 372.61760197700005 |
| suite result | 1835 / 1 failure | 1835 / 1 failure |
| passed / production_approved | false / false | false / false |

两条 run 的 `head_sha` 均为 `b5a68dc29122d5b07a2dccc0500125b48a902a96`，关联 PR30，base 为 `6010e920a168b35fccfc9ef9ee34e030b28b11d9`。这部分 run/jobs 元数据由 root 已有的 provider 查询明确转交；本验收未重复查询 run 或 jobs。其余六个 whole-job 的 success 也仅引用这份元数据，没有下载它们的 artifacts。[原始来源边界与投影](../evidence/reviews/pr30-ci-first-outcomes/first-run-metadata.json)。

PR job 的原日志明确 checkout `refs/remotes/pull/30/merge`，Git 日志显示将候选合并到上述 base。独立取得该 merge Git 对象后，核对其对象 SHA、两个父提交顺序 `[base, head]` 均一致。merge tree 与候选 head tree 均为 `11264870823132f4d851d04e505b23b2c09952b8`。当前 PR 元数据也给出同一 merge SHA；PR 仍为 open、draft、未 merged。

两个 summary 的测试前后源码清单各含 355 项，全部与候选 head 的 Git blob 内容 SHA256 匹配，两次运行的四份 before/after 清单完全相同。测试日志内容 SHA256 也分别匹配各自 summary。[源码与 merge 绑定](../evidence/reviews/pr30-ci-first-outcomes/source-pin.json)、[push checkout 投影](../evidence/reviews/pr30-ci-first-outcomes/run-44201524202-source-binding.json)、[PR checkout 投影](../evidence/reviews/pr30-ci-first-outcomes/run-44202048314-source-binding.json)。

## 原件完整性

每个失败 job 的日志各获取一次，每个 run 的 artifact 元数据各获取一次。每页元数据有 10 项；provider 接口仅返回第一页，不据此声称枚举了全部 artifacts。只选择并各下载一次下表的 Python 3.13 unit ZIP。

| Run / artifact | provider 与实际字节数 | provider 与实际 ZIP SHA256 |
| --- | ---: | --- |
| push / 14381483625 | 95389 | `53214ab2a5fea73e16d2f7703d8a980375ca96037336f03ea9ecfb871f819fb7` |
| PR / 14383105502 | 95161 | `26cbfe28cb07feb9b9e84136a6d0cbbed027ae7b7c2e6fc5d4d0a3fb00e30e04` |

每份 ZIP 均只有 `summary.json`、`worker-result.json`、`unittest.txt` 三个成员；全部成员 CRC 校验通过，未发现坏成员。成员 SHA256、大小及 CRC32 保存在[完整性证据](../evidence/reviews/pr30-ci-first-outcomes/artifact-integrity.json)。未发生解析失败，也没有重新下载任何 ZIP。

原始 provider 响应、完整原日志、ZIP 与解压原件保存在 Git 外的受限目录，目录权限 0700、文件权限 0600。本提交不含签名下载地址、凭据或私有原始材料，只保存合成摘要、源码哈希、完整脱敏失败段及绑定投影。[操作与归属记录](../evidence/reviews/pr30-ci-first-outcomes/review-ownership.json)。

## 失败内容与结论边界

两次失败均为：

```text
test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover
(test_durable_faults.ManagedProcessFaultTests)
tests/test_durable_faults.py:1456
AssertionError: bound child did not leave SH after undo within original capture horizon
```

完整 traceback 和最终 suite 结果分别保存在 [push 完整脱敏失败段](../evidence/reviews/pr30-ci-first-outcomes/run-44201524202-failure.sanitized.txt)和 [PR 完整脱敏失败段](../evidence/reviews/pr30-ci-first-outcomes/run-44202048314-failure.sanitized.txt)。两次 `unittest.txt` SHA256 分别是 `7851f7e050c01712ddf2a989dfd33703e1da844b37ff19dd5552a21ed97d0859`、`959bafbe271df63a2d8a9f35e90d985cdc03b5165c379c6c41f5c95f7e7982bb`。

该失败属于 SH 进程恢复测试；失败所在测试文件、CI 工作流及 validation runner 相比 base 均未改变。这是源码范围事实，不能据此认定失败在 base 已经存在，也不能判定其根因、归因或稳定性。

新增 `test_reserve_integer` 的 5 项测试在两份完整 unit 日志中均显示 `ok`，覆盖边界与 Decimal wire shape、冻结手算案例、fallback 值与异常类型、随机 Decimal 差分与 context 独立性、子类委托行为。其名称及结果见[合成测试摘要](../evidence/reviews/pr30-ci-first-outcomes/test-outcomes.json)。因此这两次记录没有显示整数数学测试失败；这一观察不构成整体回归通过。

候选相比 base 的 40 条变更路径中，产品源码仅新增 `uta/reserve_integer.py`，对应新增 `tests/test_reserve_integer.py`；其余为文档与证据。新模块没有接入交易 runtime，代码引用只见该测试文件。此次记录只支持 standalone 候选的上述测试观察，**不支持生产 UTA 已接入、已验收或已交付的声明**。
