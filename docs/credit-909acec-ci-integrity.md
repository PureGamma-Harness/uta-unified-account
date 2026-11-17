# 909acec：原始完整 CI 与 artifact 独立核验

结论：**本源的首次完整 CI 组件通过；整体生产验收仍为 NO_GO**。本次只收集已经自然完成的原始 CI 和文件证据，没有重跑、安装或执行包，没有打开 SQL，也没有启用长跑或真实资金。旧 dbc、460、91 的结果没有作为本源资格。

## 源身份与首次运行

源为 `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`，Git tree SHA-1 为 `cee60bc0b5413551030300e065d0dcaac6a7ff55`。PR21 实际测试合并提交为 `b221fce79e7709d6f1a36d0aff5c24225a61c084`，父提交依次为 `dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b` 和源提交，tree 与源相同。PR 原报告的 merge `code_commit`/`source_commit` 保留，没有改记为源 SHA。

push run `44132222411` 和 PR run `44132321549` 均为原 **attempt 1**，head 为本源。两个原 run 均自然完成 success，完整八个 jobs 及每一步状态保存于 `provider-jobs.json`；初始进行中与最终完成的 run 元数据分别保留。所有八个 jobs 的 unit、compile、demo、research replay、transactional acceptance、各 formal 模型、wheel build、archive verification、fresh installed verification 和 artifact retention 步骤均完成 success，核验器逐项检查，没有把跳过当作通过。

GitHub 插件优先获取 jobs/steps、artifact 元数据和原始下载引用。接口缺少独立 run 详情和 commit tree/parents 窄字段时，使用只读 `gh api` 获取。没有触发 CI rerun 或其他 provider 写入。

## 八份原始 unit 报告

每份实际报告均为 **1801 项测试、零失败、零错误、零跳过**。348 项源输入 SHA-256 映射在八份报告中完全一致，并逐项与原 Git blobs 相符。原报告均记录前后跟踪源干净、源未变化。

| 原 run | Python | summary 原计时（秒） |
| --- | --- | ---: |
| push `44132222411` | 3.10 | 358.531595456 |
| push `44132222411` | 3.11 | 458.132425654 |
| push `44132222411` | 3.12 | 403.216295408 |
| push `44132222411` | 3.13 | 392.178136763 |
| PR `44132321549` | 3.10 | 399.678127207 |
| PR `44132321549` | 3.11 | 396.778634217 |
| PR `44132321549` | 3.12 | 418.574696638 |
| PR `44132321549` | 3.13 | 322.258150250 |

三份原 members（summary、worker-result、完整 unittest）分别逐字节归档，原计时边界不归一，不作为容量成绩。

## 24 份原 artifact 与同 job 包来源

实际 provider 原清单为八份 unit、八份 package-validation、八份 wheel，共 24 份，合计 **344,627,394 字节**。所有原 ZIP 按唯一 `artifact-<ID>.zip` 命名，保存在私有目录 `/workspace/uta-ci-909acec-original-zips-unique`；逐份 provider 字节数、SHA-256、ZIP CRC 均实际核验通过。没有覆盖同名版本、没有重复解包完整源、没有发布二进制 ZIP/wheel/sdist 或临时签名下载 URL。

八份 unit 原三 members 和八份 package-validation 各十九份原文本/JSON members 已公开归档。每份 package 原报告七项 archive 检查通过、缺失和不一致为空；fresh isolated 安装各有八项测试零失败、零错误、零跳过，八个原 CLI 命令退出 0。原 `production_approved=false` 全部保留。

每份实际 wheel/sdist 与**同 run、同 Python job** 的 package manifest 及 installed-report 按 SHA-256 和大小关联，没有跨 job 拼接。额外独立核验八份 sdist 内各 **5518 个 tracked 文件**和八份 wheel 内各 **62 个 runtime 文件**，逐项与原提交 Git blobs 一致。runtime 内容清单聚合 SHA-256 为 `ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`，与 Git tree SHA-1 分开记录。

核验器仅使用标准库、`git ls-tree` 与 `git cat-file --batch` 读取原提交，未导入生产计算核心，不需要新建大冻结目录。本次证据工作树仅稀疏检出新增的 docs/evidence 路径。

## 复核、资源与发布边界

```sh
python evidence/runs/credit-909acec-ci-integrity/verify_integrity.py \
  --git-repository /workspace/uta-observer-delivery \
  --original-zip-root /workspace/uta-ci-909acec-original-zips-unique
```

Git 仓库只需持有原提交对象，当前 HEAD 无需切换。省略 `--original-zip-root` 时检查已提交原始文件、来源与报告，不声称复核未提交 ZIP/sdist。两种实际核验输出均已保存：`successor_ci_component_passed=true` 仅属于这组原 CI，`overall_acceptance=NO_GO`、`production_approved=false` 保持不变。本地完整三运行尚未收集到此证据集，将等待根集成组确认自然完成后另行追加，不继承旧源结果。

下载前实际可用空间为 18,660,986,880 字节，下载后采样为 17,341,812,736 字节；可验证时间边界记录于 `resource-observations.json`，没有编造精确采样单点时间。同宿主其他工作影响空间，差值不能全部归因于下载。该记录不是预留、后续执行授权或容量证明；原 archive 全部保留。

本提交仅增加证据、说明和只读核验器，无运行时/API/数据库/部署变更，无数据迁移，无需部署。回滚可撤销本证据提交，原 CI、ZIP、冻结源和正在运行的实验必须保留。本 CI 通过不构成全产品、万笔容量、HA、真实资金或最终上线批准。
