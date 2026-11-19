# 组合源码首轮 CI 与后续候选

原 CODE 冻结来源为 `2b1b2a6d493c3258ce0446b45959f76318cb17d6`，独立静态评审为 `eb3b12883dfd7201d5fffd95697026452ac4065f`，其中的检查范围及管理性偏差仍按原评审保留。公开交付源码 `7a4f41a6c676e2da6f63f42f30fafd5f62adfcaf` 的首次 push 和 PR 工作流现已终止，均为失败，不能继续记为 pending 或通过。

| 首次运行 | 实际测试提交 | Python 3.10–3.13 的结果 |
| --- | --- | --- |
| [push 44374507297](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44374507297) | `7a4f41a6c676e2da6f63f42f30fafd5f62adfcaf` | 四个作业均失败；每个摘要为 2298 tests、0 failures、1 error、0 skips |
| [PR 44374579916](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44374579916) | `869722c4b5ecf8f51a6bccafffe4ec7e9c3f9b10` | 四个作业均失败；每个摘要为 2298 tests、0 failures、1 error、0 skips |

PR 测试合并提交的父提交为 base `27e9442d4939465482f191fef318380dd131a2e2` 与上述 head；其 Git tree 为 `a497b811599584b63ed4a154405744d835be35cc`，与 head 相同。这是 GitHub 的测试合并对象，不是已合入默认分支。

本轮读取全部八个原作业的 provider 解码日志与步骤元数据。各 unittest 摘要记录 tracked source 前后 clean、source unchanged，worker exit 1。失败后的编译、情景、有界模型、构建与安装验证均跳过；`always()` 证据上传步骤的成功不能替代这些未执行项。本轮没有下载并独立校验原始 unit ZIP，不能把摘要读取写成 ZIP/CRC 验证或逐作业完整错误栈审计。

[独立评审](https://github.com/PureGamma-Harness/uta-unified-account/pull/65#issuecomment-6991578259) 定位原 seed 321 的等待语义差异。本轮在未修改的 `7a4f41a6` checkout 运行原五项完整比较测试，实际复现 `declared=OK / reference=OK / target=REJECT`，测试在该处停止，没有原源码完整 1024 项通过结论。原始查询输入、拒绝边界以及后续发现的响应分类差异见 [参考契约与回归](funding-hold-reference-contract.md)。

后续候选修正参考与样例，并继续复用同一 draft PR。原首轮失败不因后续测试或 CI 成功而改标，也不通过重试同一运行替代。新增源码须绑定自己的本地结果、首次 push / PR、实际测试提交和包验证；原冻结 source maps、artifact hashes 与审查限制不改写。

部署、兼容与回滚仍按 [组合交付](funding-hold-v3-combined-delivery.md)：只使用新的隔离合成工程环境，不自动采用或 reseal 既有金融权威，不迁移金融 schema。回滚前保留已确认命令、成交、仓位、资金费义务和 journal，核对未知结果后再更换 writer；删除验证代码不会消除历史失败。

本轮参考修复不启用产品、模式、权限、资金费付款或真实查询。D2 金融集成、新组件在安装包中的直接功能验证、四侧对账、复制恢复、持续 10000/s、30 分钟及长期稳定性和真实资金批准仍分别 OPEN，生产维持 NO_GO。
