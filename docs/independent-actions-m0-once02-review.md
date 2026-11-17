# once02 独立窄审：ref与政策纯控制通过，M02尚未审

固定C：`e466b67faba5fb586d68f8bd35fb7f9c7a63336e`。controller SHA-256：`74bbe8c67ef976cdfa04d7a90d5ce72dec3b3e2d15740d3db4acf785b666a196`；once workflow：`3d45991aa87caa7bbe052205a4457c8943bd7c7782318a277a2d309b9972ed84`。结论仅为 **PASS_NARROW_ONCE02_REF_POLICY_CODE_PURE**，不是M02、真实run或生产批准。

## 实际字段与负控

独立逐步读取两个workflow的literal `with` 映射，定位唯一 `path: workload`，没有复用作者的regex checker或仅搜索全文SOURCE。两处实际ref均为完整40hex `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`，checkout action精确为已审 `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`，credential persistence为false。该reader只支持本次已审plain layout，不宣称通用YAML语义或安全审计。

CPU3于 `20:38:21.436429–20:38:21.514281 UTC` 首次完成，77,868,872ns，17项纯控制、零RED：

- 两个真实workload字段通过；仅改目标ref为原36字符短抄、另一40hex或main均拒绝。once的bootstrap正确SOURCE断言和全文正确SOURCE仍然保留，不能掩盖错误checkout。
- missing/duplicate workload step以及错误的另一40hex action pin均拒绝。
- 新02政策合成内存上下文通过，旧01 ID或旧分支复用拒绝；没有创建任何真实M、marker或事件。

另直接检查旧sealed C `5a72b6abd07c5030604b596cc74e19b18ffee23e` 原workflow：正确SOURCE仍出现在bootstrap，但实际workload ref仅36字符，独立reader明确拒绝。旧失败未改为通过，见 `old-sealed-ref-rejection.json`。

## 源与授权边界

对比旧C5a72，crypto模块字节完全相同；controller除 `validate_once_manifest` 使用新REGISTRATION_ID外，其余函数AST一致。financial source909、两个业务argv、normal64/escrow96/cleanup32MiB、fresh2,348,810,240字节、四流和crypto时序没有改变。默认模板仍execution_authorized=false/C全0，Git确认C内没有actual `config/independent-m0-approved.json`。

唯一新literal分支为 `refs/heads/perf/approved-m0-20261117-02`、ID为 `independent-m0-20261117-02`；created=true/before全0/attempt1、C sole parent且仅新增marker的规则保持。实际C/M02、fresh workspace参考、完整manifest/hash与一次精确push仍须root分别审定。本review或checksum不会产生执行权，也不批准未来合入review后的新C。

## 首次实际失败继续保留

只读GitHub API独立刷新原run `44169093697`、job `134343020252`：仍completed failure，workload checkout和随后缺公共目录的verify步骤失败；runtime、pure控制、execute、upload跳过，provider artifacts为空。未rerun、删除、重建或替换原分支/attempt。

原实际M `c71ed175...` 的远端短ref失败与本地 `2bccd65...` 空sparse index删除错误是不同事件；后者被only-A检查拒绝、从未push。它们均不得被新case覆盖。完整provider log未在此复制，仅保安全步骤metadata；不把connector解码摘录说成raw provider ZIP。

未执行SQL、金融native、crypto、M0或Actions，只读取Git/AST、运行纯控制及读取平台metadata。新增公开source/privacy检查仍只属于pattern报告，不是全面安全审计。PR22及其他已知可靠性/生产阻断没有因本窄审解除，整体容量、HA、生产放行仍false。

本提交仅新增review脚本、合成结果和安全metadata，无数据库/API/部署变更。回滚为撤销review提交；所有首失败、旧分支/run、source909和旧新长任务必须保留。
