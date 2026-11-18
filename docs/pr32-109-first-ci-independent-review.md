# PR32 源码 1097387 首次 CI 独立验收

固定源码：`1097387cdb3d630f643b0ced7bf00fe4cd76028d`。两次 attempt 1 的结果分别保留：**PR 的四个 whole-job 均成功；push 的 Python 3.13 unit 仍失败，其余三个 whole-job 成功**。本次不将 PR 成功改写成 push 成功，生产批准仍为 false。

验收负责人：Codex 子代理 `/root/pr30_ci_first_outcomes`；源码范围另由 `/root/pr30_ci_first_outcomes/source_binding` 独立只读核对。没有重跑测试或 CI，没有启动 CLI、SQL、worker 或其他业务任务，也没有干预已有长测。

## 首次结果和获取范围

| Run | Event | Attempt | Whole-job 结果 |
| --- | --- | --- | --- |
| [44208918336](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44208918336) | push | 1 | 3.13 失败；3.10 / 3.11 / 3.12 成功 |
| [44208926861](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44208926861) | pull_request | 1 | 3.10 / 3.11 / 3.12 / 3.13 均成功 |

这部分 run/jobs 元数据由 root 先前的一次 provider 查询明确转交，本验收没有重复 GET run 或 jobs。[完整 job ID 与来源说明](../evidence/reviews/pr32-109-first-ci/run-job-outcomes.json)。

本验收各取一次两个 run 的 artifact 元数据，失败 push job `134481966056` 的 decoded log 取一次；只下载一次失败 push 3.13 unit artifact `14386105341`。没有下载 PR 3.13 unit ZIP 或任何成功 job 的 ZIP，因而 PR 成功仅引用 provider whole-job 结论，没有冒称验证其内部成员或实际 merge checkout。两页 artifact 元数据分别有 10、12 项；接口仅返回第一页，不据此声称枚举全部 artifacts。[元数据投影](../evidence/reviews/pr32-109-first-ci/artifact-metadata-projection.json)。

## 失败原件与源码完整性

artifact `14386105341` 的 provider 与实际大小均为 **96058 字节**，provider 与实际 ZIP SHA256 均为：

```text
6c4006813a2022468ead5d302595ee6d053a5cf36e41722efaffe7d9440f7696
```

ZIP 只有 `summary.json`、`worker-result.json`、`unittest.txt` 三个成员，全部 CRC 校验通过。成员 SHA256、CRC32 与大小见[完整性证据](../evidence/reviews/pr32-109-first-ci/artifact-integrity.json)。没有解析失败、重复下载或后续替换原件。

summary 的 `code_commit` 与 job checkout 投影均为固定源码 `1097387…`。355 项测试前后源码哈希相等，逐项与该提交 Git blob 内容 SHA256 核对全部匹配，没有缺失或不匹配。完整 `unittest.txt` SHA256 `5bdccb24f57a3a63964ef8dde86bf49b1b7f060e4065614314954456f6c600b4` 也匹配 summary。[源码 pin](../evidence/reviews/pr32-109-first-ci/source-pin.json)、[job 绑定投影](../evidence/reviews/pr32-109-first-ci/job-source-binding.json)。

候选 root tree 为 `15a07a6bd64a4e7224fc0c120137d401590ab04f`。候选与已审查的 `05c3e4d…` 的所有测试源码相同；base `6010e920…`、`05c3e4d…` 与候选的整个 `uta/` tree 均为 `4a0d5a989f0d7112454e41bbdb0162ffef34dbe4`。这是源码范围事实，不据此认定运行失败无害或已在 base 重现。

原始 provider 响应、签名下载响应、完整日志、ZIP 和原始成员均保存在 Git 外受限目录，目录 0700、文件 0600。本提交只含合成摘要、源码哈希、绑定投影及完整脱敏失败段。[归属与操作计数](../evidence/reviews/pr32-109-first-ci/review-ownership.json)。

## 实际失败及目标用例结果

失败 push unit 使用 Python 3.13.18，执行 **1842 tests / 1 failure / 0 errors / 0 skipped**，worker 退出码 1，`passed=false`、`production_approved=false`。唯一失败是：

```text
test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover
(test_durable_faults.ManagedProcessFaultTests)
tests/test_durable_faults.py:1456
AssertionError: bound child did not leave SH after undo within original capture horizon
```

这项分类来自本次原始 unit 记录，未预设为旧失败。[完整脱敏 traceback 与最终 suite 结果](../evidence/reviews/pr32-109-first-ci/failure.sanitized.txt)、[合成 unit 摘要](../evidence/reviews/pr32-109-first-ci/unit-summary.json)。它发生在 expired-SH 恢复测试，不是 AST 固定摘要断言或 CLI 启停断言。现有材料没有证明进程未离开 SH 的根因，不据此选择竞争、调度或超时解释。

同一份完整日志里，`CliFailureEvidencePureTests` 的九个方法全部各有一条 `... ok`：六项观察/cleanup 契约检查，以及原业务保留检查、`5→6` 退出等待负控、`port 0→8080` argv 负控。真实业务方法 `test_runtime_review.RuntimeReviewTests.test_cli_explicit_automation_starts_with_synthetic_policy_and_stops_cleanly` 也明确记录一条 `... ok`；没有把其他用例、旧结果或本地纯 AST 执行替代它。[全部九项及真实 CLI 原结果投影](../evidence/reviews/pr32-109-first-ci/guard-and-cli-results.json)。

这证明这些方法在本次 push 3.13 调用中通过，不证明长期稳定、任意 AST 变异检测或观察代码完全等价。旧 `497c67f…` 的六项首次 CI 失败及最初真实 CLI shutdown ERROR 均继续保留。当前 CLI 单次通过不解释或修复旧 ERROR 的原因；PR 全绿也不撤销本次 push 红或旧失败记录。
