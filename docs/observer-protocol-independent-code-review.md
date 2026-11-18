# Compact pipeline 协议身份修复：独立 CODE 闭合

固定 runtime `1a0998c2f7fdd93fbf49dccfa9a44d7fb80d42de`、提案tip `a7c9d0f8daf014efdab45d35e4cd94f2d0041cb9`。**PIPE-CODE-01按CODE关闭。** 原首次静态finding `b79d6dffee233164ab804f9fc4372ed6130bc027` 的3个文件逐字节保留，未被改写为一次实际audit结果。

## 身份与发帧分离

新增report_protocol为同一run的持久协议身份，collector_input_v2只决定watch stdout发帧。observer_command对compact-v2的watch、final-once watch与producer-audit均传相同report-protocol；仅非audit传collector-input-v2。Observer.contract据report_protocol而非emission绑定协议与六项代码SHA。因此audit不发wire，但仍重建与watch baseline相同的协议contract。

parser继续禁止producer-audit使用collector发帧，并要求watch的protocol与emission一致。legacy仍为默认。sample的baseline比较、final_check、producer_audit及其strict前置拒绝均未放宽；修复不删除baseline，也不删协议或source hash来让其通过。

只读AST确认observer的sample/final_check/producer_audit/original_command_coverage/publish及controller的classify_safely/financial_drain_before_log/resource_no_go共8个函数，与909冻结版本相同。协议contract及调用参数的变更另列为新代码；不能因这8项相同就称全部行为无变化。

## 首次运行仍未发生

source-budget的4项runtime SHA均与固定runtime commit和提案tip相同；fixture SHA `3308a5c2365920f0e51f8c33d8c1559db0571fcd475b0dd6a905b50e3d944b7d` 对应12个新方法及固定fixture commit。新增SQL-free控制包含实际contract/observer_command定义的三角色身份一致、旧legacy命令保留，以及实际sample前置baseline拒绝不同protocol。它们在本审查时仍 **NOT_RUN**，本审查者也未执行。

有界read_samples每次最多2帧、失败discard计数、EOF与retention分离、180s shutdown deadline、full消费/rollback/known-fatal drain先于CAS、同2GiB预算、final RESULT_FIELDS投影和wire SHA分域等前次CODE限定结论保留。其实际运行、落盘、故障、RSS、完整输出增长和六小时稳定性都尚未验收。

记录见 [静态闭合与来源绑定](../evidence/reviews/observer-protocol-code/static-code-closure.json)。本次没有运行新12、旧8/25、FSadapter、SQL、watch、strict audit、原数据、crypto、网络或业务进程。CODE闭合不授予首次pure或native/长测GO。

## 部署与回滚

本OWN只新增独立文档和静态记录，无服务、schema、风险参数或数据迁移。回滚移除本OWN新文件，保留原静态finding、全部首结果及原六小时NO_GO。产品输出治理、生产和真实资金批准仍为false。
