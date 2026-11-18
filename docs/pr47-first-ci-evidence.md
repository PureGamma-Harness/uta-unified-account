# PR47 首轮 CI 交付证据

PR47 的首次 push 失败，首次 PR merge 矩阵通过；不满足整轮通过门槛。源为 `05ebc17f5a2a4934a2ee27f14ecdfe0a7067bd45`，base 为 `112e5444d170a4fcdab747c4d23671058a6ec6c5`。API 取得的实际 PR merge 是 `341779921dea79d4c8d831e5bb79fa5cb5360093`，parents 为 base、head，tree `15fb593f0786affb953eeafbbecf3f44adb9dabb` 与 head 相同。两 run 均为 attempt 1，采集首读时已终态；没有重跑或追加 terminal polling。

push `44279325039` 的 Python3.10 job `134715524250` 唯一失败：2061 tests、0 failure、1 error、0 skip。错误为停止旧 owner 的恢复测试在 `publish_market(..., timeout=4)` 请求 EX 控制锁时抛出 `ServiceError`，源码错误码 `router_busy`。异常发生在五秒恢复断言之前，未进入发布主体。栈和源码不足以确定实际持锁进程、monitor 所处阶段或调度原因；原因保持 **UNDETERMINED**。

PR run `44279599639` 四个矩阵 job 均成功。固定下载的 Python3.13 job `134716479374` 报告 2061 tests、0 failure/error/skip，同名恢复测试实际为 `ok`。其余六个成功 job 仅存 metadata，不宣称其个别测试数量。实际 worker 是该 PR40 基线的严格七字段格式，不套用其他 PR 的九字段观测契约；未执行 qualification，结果为 null。

两份 unit 各 372 项 before/after source maps 与 C 字节一致；本次 Git delta 全部 108 paths 及必要源码闭包均经 Git/物理 regular 文件核对。UTA 61 个 Python 文件、tests、tools、配置和 CI/build 相对 base 没有修改。普通 unit CI 不能证明新增 benchmark observer 或组件性能已经验收。

同一成功 PR3.13 job 的小型 package 报告给出七项 checks、installed 八项测试与八条命令成功，7051 项 required paths 中覆盖全部 108 个 delta 和 169 项必要闭包。这是报告层证据；未下载约 51MB 容器或任何 wheel/sdist payload，未作二进制包审验或完整资格调用。

源码追溯区分历史通用 plan 和实际 full plan。旧 `plan.json` 的 aggregate 与 manifest pin 保留历史原值；当前 full plan SHA `03c789c6cc191c4a86af1bcf306b46830c6ca8cbf1b3394673168833c034f21c`、控制脚本、当前/原始目标的 manifest 及既有公开 SAFE 收据 66 项源码闭包匹配 C。此轮只做静态比对，不重新审验旧私有六库原件，不将该组件结果用作首 CI 的替代证据。

全部三份原 ZIP 合计 250487B，长度和 provider SHA 均匹配，25 个 member CRC 通过。原 ZIP、unit members、完整日志、真实 helper/profile 绑定和下载引用均留私有。公开文件只保留有限 metadata、类型/计数、public source 行与 hash 收据。派生过程中的行政守卫与格式假设错误单独保留，没有补跑目标或重新下载。独立 RAW 复核仍 **PENDING**。

本提交仅新增 [有限安全证据目录](../evidence/runs/pr47-first-ci/README.md) 和本说明，没有修改运行时代码、测试、workflow、旧 authority 或历史记录。不会部署程序或迁移数据；回滚只需移除此证据提交并保留私有原件与审计历史。金融启用、生产、容量和性能验收均为 false。后续修复与新的首轮验证必须使用各自的新 source/run 记录。
