# M05 push 的 general CI 首结果：四 runtime 包验证失败

[run 44217339023](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44217339023) 的 attempt 1 已终态 `failure`，head 为 `cad6e2b8e5efbb13da66376f69ce9dca39e522ba` / tree `74904725972f6b8b6b7966159fe0d6ac30bb3546`，workflow 为 `.github/workflows/ci.yml`。首观察为 in_progress，未 rerun、dispatch、push 或取消。这里仅收集已获授权自动 CI 的只读结果，没有在本地执行产品、测试、SQL、native owner 或打包。

| Matrix | 实际 CPython | SQLite | Unit 首结果 | Exact sdist/wheel | Installed validation |
| --- | --- | --- | --- | --- | --- |
| 3.10 | 3.10.22 | 3.46.1 | 2049 PASS，0 failure/error/skip | FAIL | SKIPPED |
| 3.11 | 3.11.18 | 3.46.1 | 2049 PASS，0 failure/error/skip | FAIL | SKIPPED |
| 3.12 | 3.12.16 | 3.46.1 | 2049 PASS，0 failure/error/skip | FAIL | SKIPPED |
| 3.13 | 3.13.18 | 3.46.1 | 2049 PASS，0 failure/error/skip | FAIL | SKIPPED |

四个 unit report 都记录 worker exit 0、source unchanged、tracked source 前后 clean。Compile、demo、research replay、acceptance、各 bounded formal 探索和 wheel build 的 provider step 均 success；这保留各步骤的实际范围，不构成 general CI 整体通过或容量/生产批准。

四个 job 都在 step 19 `Build and verify exact source distribution and wheel` 首次 exit 1。原 verifier 七检查中 `sdist_required_files_exact=false`，其余六项 true；相同缺项为：

- `evidence/independent-m0-entry-type-provenance/pure-once01/inputs.sha256`
- `evidence/independent-m0-scan-proof/pure-once01/inputs.sha256`

静态 Git 核对证明两项都在实际 M 的 tracked tree。verifier 的发布合约要求全部 tracked source/evidence，当前 MANIFEST 的 evidence 扩展名列表没有 `*.sha256`。本 OWN 没有修改 MANIFEST、放宽合约、重新 build 或重跑旧 source。后续 installed-package 验证与 review-artifact 上传被 skip，不能写成通过；always 上传步骤 success 也不证明未运行的 installed 验证成功。

`evidence/m05-general-ci-first/` 保留首/首 job-terminal/首整体 terminal API JSON、完整 jobs/steps、四份完整 decoded UTF-8 job logs 和从日志提取的 unit/package report。四份日志共 8,947,812 字节；长度按 connector 返回的 UTF-8 内容独立核对，SHA256 和全部文件清单在 `seal.json`。这不是原始 HTTP ZIP 字节验证；unit artifact ZIP 未下载，本结论依据 provider API 与完整 job console，不冒称独立读取了 artifact 中完整 unittest 文件。

M05 once run `44217339075` 由另一个 owner 负责，本 owner 未查询、下载或解释它。这里的 general CI 四 runtime 结果不能替代 once 的冷导入 219-method guard 记录、实际 B/P 结果或 CMS/artifact 审查。原 4e 首失败、G 首 stub、d58 首通过和所有旧 M01–M04 结果不改。

本证据分支只从 C `933c86803020fccbc11949795cb9c75a2262959d` 增加 docs/json/text，没有把实际 M 作为祖先、带入 true marker 或改变业务 runtime。回滚只移除新增报告引用并保留首证据；生产、10k/s、HA、真实资金及 general CI acceptance 均 false。
