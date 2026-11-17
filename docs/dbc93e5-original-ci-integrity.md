# dbc93e5 原始 CI：NO_GO

push `44125869999` 和 PR `44125881372` 的 Python 3.10 jobs 均在 `Run unit tests` 失败：各 **1801 项、零 FAIL、11 ERROR、零跳过**。两份完整原始输出及十一项异常的逐项索引已保留，没有重跑、删错或调整结果。其余六个 jobs 原始结果为 success。

十项错误来自 `test_ledger_main_acceptance.IndependentMainAcceptance` 的 test_01、02、03、04、05、06、07、08、12、14，均在 helper `joined` 第 137 行查询 `PRAGMA query_only` 时出现 `sqlite3.DatabaseError: not authorized`；另一个来自 `test_ledger_main_schema.LedgerMainSchemaTests.test_ms002_healthy_temp_copies_need_no_temp_read_permission`，helper 第 112 行进入 `snapshot` 第 52 行查询 `main.sqlite_master` 时出现同类错误。完整名称、原 log 行号和各自 traceback 保存于 `priority-python310-errors.json`，保持原始顺序和文本。

失败后 compile、demo、research replay、transactional acceptance、各 formal 模型、build、package 和 installed 验证步骤全部跳过，不能记为这些链路通过。实际 provider 只有 **20 份 artifact：八 unit、六 package-validation、六 wheel**。没有第七或第八份包证据，不补造缺档。

源为 `dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b`，实际 Git tree SHA-1 为 `9b30f41b9df52efbe8eb56d0c7af958594bcf1f9`。PR 测试合并提交为 `4c78b658714a6e0b6d235aca987f06966d2226f0`，父提交为 `91e4ae40b5e9b884c54026406299df5000c9c100` 和源提交，tree 与源相同。

两个失败报告各有 348 项输入 SHA-256，已逐项对原提交的 Git blobs 核对一致。原提交实际有 5159 个 tracked 文件、62 个 runtime 文件；runtime 清单聚合 SHA-256 为 `ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`，与 Git tree SHA-1 分开记录。核验读取 Git objects，不新增大冻结目录、不导入生产核心或打开数据库。

本证据提交不改运行时、API、数据库或部署，无数据迁移，无需部署。回滚只需撤销证据提交，原始失败、原 ZIP、旧记录、冻结源和正在运行的实验必须保留。新修复必须用新 SHA 独立验收；本轮结果始终为 **NO_GO**。其余原 artifact 的完整性在全部下载后追加，不据未完成的收集声称通过。
