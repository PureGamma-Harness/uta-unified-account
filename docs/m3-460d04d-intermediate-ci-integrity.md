# M3 中间源 460d04d：CI 原件与来源核验

结论：**此中间源 CI 组件通过；整体验收仍为 NO_GO**。这是对已完成原始 CI 的只读收集和文件核验，不是新测试运行。没有本轮 M3 本地完整三运行证明，也没有后续 F02 修复源、生产容量、HA 或真实资金批准。该源的原 F02 问题仍未解除，不能用八个绿色 CI jobs 覆盖独立验收阻断。

## 原始来源

源提交为 `460d04d19ea2beb55a3f6efd8eb516ba257804cc`，Git tree 为 `c9d882cfbc9348be627324a8fa1daf3d590b14ce`。PR19 原测试合并提交为 `e5185f7f066f3464d2ca36bd770643ab7d94f96b`，父提交分别为 `91e4ae40b5e9b884c54026406299df5000c9c100` 和 `460d04d...`；其 tree 与源提交相同。源提交、合并提交及父提交分别保留在原始报告和窄字段来源文件中，没有把 PR 包的 `source_commit` 改记为源提交。

GitHub 插件优先获取两个原 run 的完整 jobs/steps、artifact 元数据和原 ZIP 下载引用。commit tree/parents 窄字段另用 `gh api .../git/commits/<SHA>` 获取。没有创建新的冻结目录；独立核验器通过 `git ls-tree` 和 `git cat-file --batch` 直接读取原提交的 blobs，不依赖当前工作树内容。

## 八个原始 jobs

push run `44117708873` 和 PR run `44117719057` 各有四个已自然完成的 success jobs。八份实际 summary 均为 **1762 项测试，零失败、零错误、零跳过**，输入摘要各 342 项；这八份摘要映射完全一致，并逐项与原 Git blobs 相符。原始报告均记录源未变更且前后跟踪源干净。

| 原 run | Python | summary 原计时（秒） |
| --- | --- | ---: |
| push `44117708873` | 3.10 | 368.283411078 |
| push `44117708873` | 3.11 | 354.479642352 |
| push `44117708873` | 3.12 | 404.132856760 |
| push `44117708873` | 3.13 | 417.815393453 |
| PR `44117719057` | 3.10 | 397.081595778 |
| PR `44117719057` | 3.11 | 411.661339647 |
| PR `44117719057` | 3.12 | 402.024599714 |
| PR `44117719057` | 3.13 | 432.102405129 |

各自 `summary.json`、`worker-result.json`、完整 `unittest.txt` 逐字节保留。计时字段没有归一、替换或用作吞吐结果。

## 24 份原 artifact 与包

实际 provider 清单为八份 unit、八份 package-validation、八份 wheel artifact，共 24 份，没有猜测或补造缺失档。全部原 ZIP 按 `artifact-<ID>.zip` 唯一命名，保留在私有本地目录 `/workspace/uta-ci-m3-460-original-zips-unique`；没有使用会把 `.10/.11/.12/.13` 改成相同文件名的 `with_suffix`。

24 份 ZIP 共 305,781,028 字节，每份 provider 原始字节数、SHA-256 与 CRC 均实际核验通过。八份 unit 各三份原 members，八份 package-validation 各 19 份原文本/JSON members，合计 176 份原始安全文件已入库。八份 wheel artifact 的二进制 wheel/sdist 留在私有原 ZIP，不加入 Git。

每份 wheel/sdist 都与**同 run、同 Python job** 的 package manifest 和 installed-report 按字节数、SHA-256 对应，没有跨 job 拼接。八份 package 原报告均为七项 archive 检查通过、缺失和不一致为空；fresh isolated 安装各有八项测试零失败、零错误、零跳过，八个原 CLI 命令退出 0。全部保留原 `production_approved=false`。

独立文件核验额外验证八份实际 sdist 各 **4466 个 tracked 文件**与原提交逐文件 SHA-256 一致，八份实际 wheel 各 **62 个 runtime 文件**与原提交一致。62 是文件数，不是口头模块数量。runtime 映射的聚合 SHA-256 为 `15c1c09c2ece80d0007f694dd501fd2794e76170c3b3087f99d460c483842718`。独立核验没有导入生产计算函数、安装或执行包，也没有打开 SQL 数据库。

## 重复核验及资源边界

```sh
python evidence/runs/m3-460d04d-ci-integrity/verify_integrity.py \
  --git-repository /workspace/uta-observer-delivery \
  --original-zip-root /workspace/uta-ci-m3-460-original-zips-unique
```

指定的 Git 仓库只需持有原提交对象，当前 HEAD 不需切到该源。省略 `--original-zip-root` 时仍核验已提交 raw members、342 项源摘要、原 package 报告与 Git 原提交，输出不会声称核验未提交 ZIP 或 sdist。两种实际核验输出均已保存。

收集前原 `df -B1` 可用空间为 16,828,166,144 字节，收集后的只读采样为 16,383,172,608 字节；采样时间及条件记录于 `resource-observations.json`。两者包含同宿主其他工作的影响，差值不能全归因于下载。没有删除任何原 archive，没有操作原实验；这些数值不是资源预留、后续执行授权或容量验收。

## 部署、兼容与回滚

本提交只新增证据、说明和只读核验器；无数据库迁移、API 或部署变更，无需部署。撤销本证据提交即可回滚工作树，原始 CI 结果、原 ZIP、旧证据和各实验必须保留。

这组 CI 仅属于中间源 `460d04d`，不会改变 M3 关闭默认入口、公开 managed 借贷拒绝及 readiness/升级限制，也不会解除原 F02 阻断。后续 F02 修复源需要新的 SHA、实际测试、包与独立验收；不能继承本源的绿色结果。
