# PR50 首次 CI 证据

公开源 `2cf04629e3b724ea3d9a46ae83e6ff10ea6750ee` 的首次 push/PR，attempt 均为 1，均失败。固定 push3.13 原件 2061 / 0F / 0E；固定 PR3.13 为 2061 / 1F / 0E；唯一额外失败 push3.12 原件为 2061 / 0F / 1E，全部 0 skip。

两个原始失败分别是持久行情内容改变后的 `financial_ready` 断言，以及启动上下文进入时的 `lease_expired`；根因保持未决。失败 job 的后续验收步骤未运行。本交付不重跑、不改阈值、不将成功 job 的打包结果补记给失败 job。

完整有限证据、源码绑定、失败投影、下载预算和私有封存收据见 [evidence README](../evidence/runs/pr50-first-ci/README.md)。独立 RAW 复核 PENDING；真实资金、容量与生产验收均未批准。
