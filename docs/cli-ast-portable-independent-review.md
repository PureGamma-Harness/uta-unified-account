# CLI AST 契约修复独立 CODE 审查

固定审查源码：`05c3e4d5a4124e4a2185c621071f1a9890d10d0b`。本次未发现阻塞这次同解释器 AST 表示契约修正的问题。结论只覆盖冻结来源、当前业务内容及已有纯 AST 执行记录；不构成 CLI shutdown 修复、完整 CI 通过或生产批准。

负责人：Codex 子代理 `/root/pr30_ci_first_outcomes`；语义范围另由 `/root/pr30_ci_first_outcomes/source_binding` 独立核对。此次仅做 Git、源码、静态 AST 提取和文件哈希检查，没有运行任何测试、规范化函数、CLI、SQL、signal、CI 或网络操作，没有修改作者工作树，也没有重新读取或下载 PR30 ZIP。

## 冻结来源与修正内容

父链为 `497c67f… → dfb7f998… → 05c3e4d…`。前一提交增加冻结原方法的 JSON；后一提交只修改 `tests/test_cli_sigterm_failure_evidence.py` 的契约检查和两个负控。旧 `original-case-ast.json` 的固定摘要 `a5884f2d24313698722277f803206c460aa1ef7e2a38055dfdae7820df01d128` 仍原字节保留，未改写历史失败证据。

冻结 JSON 的 `method_source` 与 `6b7d473c0fbf92b17c146140c88eb2c25d38dce1:tests/test_runtime_review.py` 中原方法的源文本逐字一致：

| 绑定 | 已核对值 |
| --- | --- |
| 原 Git blob | `b7ca53a9124fef1e74d5eb30779109a88d841bde` |
| 原完整文件 SHA256 | `d86b9b63e6fa30d9527ccec25c3ac03ad33826f0e94365962dd35cef024cede9` |
| 原方法文本 SHA256 | `78f4c55535c9e4718202004a4369aff3d21573db70eb9a50a6283e12828537bc` |

新检查先校验冻结方法文本的 SHA256，再用同一实际运行解释器分别解析冻结原方法和当前方法，比较规范化 AST。它不再要求不同 Python 版本的 `ast.dump` 字符串具有同一摘要，也没有为各版本硬填预期摘要。[完整源码 pin 与哈希](../evidence/reviews/cli-ast-portable-independent/source-pin.json)。

## 当前业务内容与覆盖边界

人工核对 `tests/test_runtime_review.py:146–210`：原启动、健康检查、退出等待的 `5/3/5` 秒预算和 fallback `communicate(timeout=5)` 均保持；CLI argv（含 `--automate --port 0`）、cwd、环境、数据库重开与业务断言均保持。当前异常处理最后仍为裸 `raise`。此前明确记录的 IO 观察差异只有移除 `text=True`、增加 `bufsize=0`；`05c3e4d` 没有再改 IO 或该业务方法。`6b7d473…`、旧 PR32 head `497c67f…` 与本次固定源码的整个 `uta/` tree 相同。

两个新增负控分别把退出等待 `5→6`、CLI `port 0→8080`。两处替换在当前文件各匹配一次，修改的是被比较器保留的业务常量，能约束这两类具体变化。

规范化器本次没有改变，其既有排除范围仍需明确：顶层 `Try` 仅保留 `body`，不比较 `handlers/orelse/finalbody`；同时排除 cleanup 定义、允许的 cleanup 注册、观察 import、`evidence/primary_error` 赋值、`evidence.*` 调用和 Popen 的两项 IO keyword。因此，把被排除 handler 的裸 `raise` 改为 `pass` 等变化，可能不被此比较器发现。两个负控不构成任意业务变异、异常路径或观察函数等价的完备证明。本次另行读取了当前排除区域，没有发现当前源码吞掉原异常；这不扩大比较器本身的覆盖范围。[CODE 审查与具体边界](../evidence/reviews/cli-ast-portable-independent/code-review.json)。

## 已有首次纯 AST 记录

原 `first-results.json` 的 SHA256 是 `197775f578b5b6a97b6753e2b34c63d7d2dcb0af3e95117a0e9de2874b7df392`，其 `source_commit` 声明为本次固定源码。以下是 root 先前执行留下的记录，本审查没有重跑：

| Runtime label | 原 stderr 结果 | stdout 字节数 | 原记录 binary SHA256 与现存文件 |
| --- | --- | ---: | --- |
| python310 | 3 tests / OK | 0 | 匹配 `473dd9c9…19c9989` |
| python312 | 3 tests / OK | 0 | 匹配 `fa674435…15d5ea7` |
| python313 | 3 tests / OK | 0 | 匹配 `889c603f…5d797d9` |

三组 stderr 都仅列出原方法保留检查及上述两个负控，原记录退出码均为 0；六份 stdout/stderr 的实际哈希全部匹配原清单。三个 binary 的绝对路径由 root 明确转交，本审查只读取现存 binary 字节做 SHA256，没有执行它们。原记录没有 Python 3.11 这一批的本地执行结果，不把三组记录写成四版本验收。原 JSON 的源码绑定是其声明，本审查另行 pin Git 源码，不将其扩张为逐进程源码轨迹证明。[逐项原记录核验](../evidence/reviews/cli-ast-portable-independent/first-records-verification.json)。

旧 PR32 首次六项 CI 失败仍由 `c61ee1ba577d981ca0de2cbdc26de502f8519d59` 保留：它们是旧固定 AST 摘要的证据测试失败，不是新原生 CLI shutdown 失败。最初真实 CLI 的 shutdown ERROR 原因仍未知，本次修正不解释它，也不撤销它。新源码的完整 CI 结果需要独立保留；本审查没有提前给出通过结论。生产批准保持 false。[归属与操作范围](../evidence/reviews/cli-ast-portable-independent/review-ownership.json)。
