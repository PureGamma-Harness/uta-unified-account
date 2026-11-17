# 自动包验收工作流的独立静态审查

审查对象为不可变提交 `1eaefb89e0e161033abcd41b8538a7284657f20f`，从 Git blob
读取工作流及其已存在的 verifier、installed checker、CLI helper。本审查与行情候选
交付无关；其提交仅包含本文及独立静态证据，可以单独 cherry-pick 到 M2/NEXT，不能
因此合入候选运行时。

结论：**声明的 CI 包验收合同范围内未发现静态阻断项**。这只确认配置及调用关系，
没有执行构建、安装、workflow、SQL、服务或测试，不构成任何包结果、生产或 M2 放行。

## 步骤依赖与实际提交身份

四个 Python 版本继续使用独立 `ubuntu-latest` matrix job。每个 job 顺序执行：原有
测试/模型 → wheel → sdist 与精确 archive verifier → fresh venv 的安装验收 →
`always()` 报告保留 → 成功时的 wheel/sdist 审阅制品。新增验证步骤没有
`continue-on-error` 或放宽成功条件；前置失败阻止后续安装验收。报告上传的 `warn`
只容许报告未生成，不把之前失败改成成功。

`checkout@v4` 没有覆写 `ref`，精确 verifier 使用 `--commit "$GITHUB_SHA"`，
并要求 checkout HEAD 与该 commit 相同、tracked 文件无差异且无未忽略的 source。
因此 PR 运行按 GitHub 的实际 merge commit 绑定，不会替换成 PR head SHA。具体
merge SHA、成功 job 数和结果仍须由首次实际 workflow 的原始报告证明。

shell 传入 `dist/*.whl` 与 `dist/*.tar.gz`；二者各是 verifier 的单个必需 Path 参数。
预期每种仅一个制品，多匹配会成为额外 argparse 参数而失败，零匹配则无法打开该路径，
没有取第一个制品或静默降级的逻辑。archive verifier核对所有 tracked source/evidence
的 sdist 字节、wheel/sdist runtime map、版本、entry points 及已有 legacy fixture。
这不等于在本次静态审查中实际构建了任何制品。

## 安装隔离与八项功能合同

安装步骤先建 venv、安装 wheel，再切到 `$RUNNER_TEMP`。新增 checker 以 fresh venv
的 `python -I`、`env -u PYTHONPATH` 执行；它拒绝 source 作为导入位置，并核对已安装
runtime map、版本与实际 console targets。工作流未传 `--identity-only`。

已有 helper 的 7 个 `test_*` 与显式增加的 1 个金融协议 case 合为预期 8 项。checker
要求 `wasSuccessful()`、`testsRun == 8` 且无 skip。该额外 case 检查订单已接受后的
预占、原 CID 的丢失回复重查/重试、新父恢复及离线撤单与余额；不能据此宣称成交吞吐。
helper 仅把子进程 cwd 的 ROOT 指向 installed site-packages；金融函数未被替换。
verifier 必须先成功才允许 checker 读取其 manifest，这是本工作流保留的必要依赖。

## 报告 allowlist 与私有状态

`always()` 仅上传以下已知报告：archive manifest、`installed-report.json`、
`installed-cli-tests.txt` 及 installed-validation 目录**直接子文件**中的
`uta*.stdout.txt` / `uta*.stderr.txt`。没有整个输出目录或 `**` 递归上传。

因此 `empty-cli-authority` 下的 SQLite/WAL/SHM、先前 smoke authority、auth DB、
signing JSON、证书和 TLS key 文件都不在匹配范围内。静态模式检查也核对了常见这些
私有路径不会匹配，而普通 console stdout 会匹配。该判断是上传文件范围审查，不把
它冒称为对未来所有报告内容的运行时保密验收。wheel/sdist 另以两个 `dist/` 模式保留，
不是私有 authority 的目录归档。

## 改动、回滚与证据限度

目标 commit 只改 `.github/workflows/ci.yml` 和说明文档，没有 runtime、金融规则、
数据库 schema 或迁移改动。回滚只恢复后续 CI workflow，保留既有失败证据；不能
恢复旧 workflow 就审批尚未验证的包。

静态检查用 PyYAML `BaseLoader` 解析原 YAML，逐个原 run block 执行
`bash --noprofile --norc -n`，并对 Python heredoc 只做 AST 语法解析。没有运行这些命令。
精确输入 SHA-256、检查数、步骤顺序和 allowlist 见
[静态证据](../evidence/runs/ci-package-gates-static-review/static-checks.json)。
实际 CI、安装产物、完整 release、容量、故障恢复及真实资金审批仍是单独门槛。
