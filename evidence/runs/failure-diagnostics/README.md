# Failure diagnostics 小规模证据

基线 `21aa6510bafcce8383fc24ac2c35e671074b9baf`，隔离 worktree `/workspace/uta-failure-diagnostics`，分支 `feat/failure-diagnostics`。未运行负载、soak 或大型 fixture，没有修改旧 24h 作业。

- `red.txt`：修改运行时代码前的真实 red，旧 caller 调用成功并存有 generic attempts/last_error，但没有任何 cause event；断言 `0 != 1`。命令为单 CPU `python -m unittest tests.test_failure_diagnostics.FailureDiagnosticTests.test_legacy_caller_retains_generic_fields_and_explicit_missing_cause -v`。
- `final-20261117T065422.txt` / `.json`：最终 71/71 通过、11.096 秒；JSON 记录实际 UTC、cwd、完整 argv、1 CPU affinity、base head、当时 tracked diff 摘要与退出码。覆盖新 focused 13 例、原 durable commands、independent reference、v2 views / v1 role HTTP 及真实 spawn poison worker。`tested-source-sha256.json` 记录最终被测 runtime/tests 字节摘要。最终 runner 用 `open('x')` 保存输出和元数据，拒绝覆盖已有文件。
- `green-focused.txt`：中间版本独立 focused 12/12 通过；不是最终全部验证。
- `regression-before-additive-expectation.txt`：真实中间回归失败。原 independent test 将全部 `uta_events` 当作金融状态不变，新增合法 global event 使全表相等断言失败。修正只在**先独立断言唯一诊断事件的 NULL account / v1 / 原 CID / attempt / missing-cause** 后移除该新增类型，再逐表比较全部原金融 rows 与全部原事件；没有放松金融效果断言。
- `intermediate-additive-test-import-error.txt`：下一轮真实 71 例运行中，新增测试缺少 `import json` 导致唯一 NameError；已修复并由最终整组验证覆盖。

首次 focused 运行另有一个测试 fixture 错误：`financial()` 把随合法事务更新的 `writer_fence_lease.observed_ns` 也纳入金融不变比较。**首次错误的输出文件后来被覆盖，原 raw 已不可用**；会话中曾展示该输出，但不能把转录当作仍存在的原 artifact。`fixture-red-reproduction.txt` 是后来在真实环境按原错误 selector 精确重跑产生的输出，明确不是首次 raw；其独立 metadata 记录该文件的实际 mtime、登记时间、source digest 和 provenance，未补造旧时间。heredoc 的完整 source 保存在 `fixture-red-reproduction-source.py`；原命令为：

```sh
taskset -c "$(python -c 'import os; print(min(os.sched_getaffinity(0)))')" python - <<'PY' > evidence/runs/failure-diagnostics/fixture-red-reproduction.txt 2>&1
# 完整 Python source 见 fixture-red-reproduction-source.py
PY
```

最终 fixture 比较 `uta_*` / `ledger_*` 金融表，明确排除单独断言的 inbox 与 events；保留金融 effects、terminal、attempt 与 event 原子断言。测试不依赖 lease observation 时间不变。

独立只读 peer review 在首次 focused 10/10 通过后发现 dict subclass / metaclass / 非字符串字典 key / frame globals 的任意 hook 及损坏 persisted kind 无界风险。最终实现改为 native descriptors、identity 比较、最多 16 个 native items 的 exact-str 键筛选，以及已知 kind / 原文本摘要；新 adversarial tests 覆盖。peer 最终单 CPU 独立验证 focused 13 + HTTP 1 共 14/14 通过，并另复跑 3 个关键边界，未见剩余阻断项。此为工程审查结论，不是生产性能批准。
