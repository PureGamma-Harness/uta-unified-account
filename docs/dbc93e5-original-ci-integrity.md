# dbc93e5 原始 CI：NO_GO

push `44125869999` 和 PR `44125881372` 的 Python 3.10 jobs 均在 `Run unit tests` 失败：各 **1801 项、零 FAIL、11 ERROR、零跳过**。两份完整原始输出及十一项异常的逐项索引已保留，没有重跑、删错或调整结果。其余六个 jobs 原始结果为 success。

十项错误来自 `test_ledger_main_acceptance.IndependentMainAcceptance` 的 test_01、02、03、04、05、06、07、08、12、14，均在 helper `joined` 第 137 行查询 `PRAGMA query_only` 时出现 `sqlite3.DatabaseError: not authorized`；另一个来自 `test_ledger_main_schema.LedgerMainSchemaTests.test_ms002_healthy_temp_copies_need_no_temp_read_permission`，helper 第 112 行进入 `snapshot` 第 52 行查询 `main.sqlite_master` 时出现同类错误。完整名称、原 log 行号和各自 traceback 保存于 `priority-python310-errors.json`，保持原始顺序和文本。

失败后 compile、demo、research replay、transactional acceptance、各 formal 模型、build、package 和 installed 验证步骤全部跳过，不能记为这些链路通过。实际 provider 只有 **20 份 artifact：八 unit、六 package-validation、六 wheel**。没有第七或第八份包证据，不补造缺档。

源为 `dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b`，实际 Git tree SHA-1 为 `9b30f41b9df52efbe8eb56d0c7af958594bcf1f9`。PR 测试合并提交为 `4c78b658714a6e0b6d235aca987f06966d2226f0`，父提交为 `91e4ae40b5e9b884c54026406299df5000c9c100` 和源提交，tree 与源相同。

两个失败报告各有 348 项输入 SHA-256，已逐项对原提交的 Git blobs 核对一致。原提交实际有 5159 个 tracked 文件、62 个 runtime 文件；runtime 清单聚合 SHA-256 为 `ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`，与 Git tree SHA-1 分开记录。核验读取 Git objects，不新增大冻结目录、不导入生产核心或打开数据库。

## 全部实际 artifact 的完整性

实际二十份 provider 原 ZIP 均已按唯一 `artifact-<ID>.zip` 文件名保存于 `/workspace/uta-ci-dbc93e5-original-zips-unique`，合计 244,207,198 字节，逐份 provider SHA-256、原始字节数、ZIP CRC 均核对通过。八份 unit 原始三 members、六份 package-validation 各十九份原文本/JSON members 均逐字节入库；六份 wheel artifact 内原 wheel/sdist 二进制仅留私有 ZIP，没有加入 Git。没有保存或发布临时签名下载 URL。

八份 unit 原报告均实际执行 1801 项，源输入摘要各 348 项、映射完全一致并逐项与原提交 blobs 相符；前后跟踪源干净、源未变化。六份成功的 package 报告各七项 archive 检查通过、缺失和不一致为空，fresh isolated 安装各有八项测试零失败、零错误、零跳过及八个 CLI 命令退出 0。

六份 wheel/sdist 均按**同 run、同 Python job** 对应原 package manifest 和 installed-report 的 SHA-256、字节数；原 PR 报告的 merge `source_commit` 原值保留。只读核验额外验证六份 sdist 各 5159 个 tracked 文件和六份 wheel 各 62 个 runtime 文件与原 Git blobs 逐文件一致。它们不能补足两个失败 jobs 被跳过的 compile、demo、replay、formal、package 或 install 步骤。

完整八个 jobs 的所有原始步骤状态均保留在 `provider-jobs.json`，包括六个成功 jobs 的 compile/demo/replay/formal/package/install 完成状态，以及两个失败 jobs 的失败和跳过状态。仅根据真实 provider 元数据和原 artifact 报告记录，不重跑任何步骤。

```sh
python evidence/runs/dbc93e5-ci-integrity/verify_integrity.py \
  --git-repository /workspace/uta-observer-delivery \
  --original-zip-root /workspace/uta-ci-dbc93e5-original-zips-unique
```

省略 `--original-zip-root` 时核验已提交 raw、原报告和原 Git blobs，不声称复核未提交 ZIP。包含原 ZIP 和仅已提交 members 两种实际核验输出均保留：`integrity_passed=true` 只代表这些文件和来源检查通过，`final_source_ci_passed=false`、`overall_acceptance=NO_GO`、`production_approved=false` 保持不变。

## 原本地完整三运行封存

根集成组原外部矩阵从 `2026-11-17T16:27:02.425424+00:00` 到 `16:47:30.559308` 自然完成，固定 CPU 1、共享宿主，顺序为 3.12、3.10、3.13。没有取消、重启、重跑或修改原作业。

| 原本地运行 | 实际测试 | FAIL | ERROR | 跳过 | 退出码 | worker 秒数 | summary 秒数 | 外部矩阵秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Python 3.12 | 1801 | 0 | 0 | 0 | 0 | 389.864 | 391.164003123 | 391.314390568 |
| Python 3.10 | 1801 | 0 | 11 | 0 | 1 | 426.677 | 427.662976296 | 427.833145402 |
| Python 3.13 / SQLite 3.46 | 1801 | 0 | 0 | 0 | 0 | 407.638 | 408.759141052 | 408.875393733 |

三种计时边界分开保留，没有互相替代。三份原 `summary.json`、`worker-result.json`、完整 `unittest.txt`、所有原启动日志、矩阵 progress/summary 均逐字节归档并列出大小与 SHA-256。原矩阵记录 `source_clean_after=true`、`all_exit_zero=false`；每份报告均记录前后跟踪源干净、源未改变。三份原 348 项输入映射与八份 CI 及原 Git blobs 完全一致。

原外部 launcher `/workspace/run_uta_final_matrix.py` 的完整字节保存在 `local/execution-driver.py`，SHA-256 为 `8b40d75bb5f1569ebdc4c098bc6d5a01b5b3160a9b05a4bc34c93e6c8da93bd8`，与原矩阵记录一致。核验只读取已经结束的原文件，没有执行此 launcher。

此前 CI-only 完整性输出保持原样，追加带 `local-complete` 文件名的两种实际只读核验结果。它们记录三轮原本地运行已收集、`local_full_matrix_passed=false`；CI 六绿和本地两绿均不能覆盖三个 Python3.10 原 11 ERROR 结果，整体仍为 **NO_GO**。

## 资源、部署与回滚

下载前实际可用空间为 17,677,639,680 字节，下载后只读采样为 16,688,234,496 字节；两次采样条件与可验证时间边界记录在 `resource-observations.json`。同宿主其他工作也影响空间，不能把差值全部归因于下载。没有删除任何原 archive，也没有授权后续资源消耗或启用长跑。

本证据提交不改运行时、API、数据库或部署，无数据迁移，无需部署。回滚只需撤销证据提交，原始失败、原 ZIP、旧记录、冻结源和正在运行的实验必须保留。新修复必须用新 SHA 独立验收；本轮结果始终为 **NO_GO**。
