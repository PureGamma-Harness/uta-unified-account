# 资源豁免必须来自显式角色，不能由树名推断

独立OWN `caf052b3d92c7d278500edb2d1c5f8390145a2f5` 完整pick为98666ac，保留d073的131 PASS及后续原3个真实tinyfile探针：合法private/B/workload为正例，public/case-B-safe/B/workload和private/B/P/workload两个错误返回1，首2RED/1positive原167,752,191ns及源/hash/stdout均未改变。这是case_bytes第二计量窗口的policy上下文放宽，不是M02首失败原因，也不称金融exploit；resource_usage全局扫描先前会拒公共路径，不能用那一事实掩盖case_bytes后续独立窗口错误。

最小修复只将内部anchor改为显式 `(role, anchor)`。`private_root`只接受`[BP]/workload/authority/shard-NNNN.sqlite3-(wal|shm)`和`runtime-probe/private.sqlite3-(wal|shm)`；`private_case`只接受`workload/authority/shard-NNNN.sqlite3-(wal|shm)`。两种布局互斥，不再检查anchor.basename是否叫B/P来猜权限。tree_bytes默认没有SQLite重扫角色；case_bytes明确只向private/name传private_case，公共case-safe树不传角色；case_pipeline私有case同样显式private_case，staged树无角色。resource_usage只给其private输入private_root，不向public发角色。角色由已审内部调用点授予，不是对外客户参数或目录命名权限。

原≤3轮、50ms准入/完成边界、非aux稳定路径/类型保留、regular保守max尺寸、逐entry额度、原56+2+2/60秒检查均不改变。missing/权限/EIO/目录/symlink/未知名保持拒绝；不增加SQLite或observer临时名白名单，不改变source909、crypto、业务argv或预算。新增4个pure scope边界，合计135 pure PASS；合法private_case正例通过实际case_bytes调用验证，泛型tree未授角色时也拒绝同一消失事件。

独立原首RED夹具保持原pin/d073，不改造成通过；新控制版本另留source-bound结果。没有native、SQL、crypto、M03、触发分支、push或dispatch；03仍defaultfalse模板和外部false提案，workspace参考留root实际登记前采集。M01、M02 UNKNOWN/P NOT_RUN、PR22恢复ERROR、旧24h提前退出均保留，生产/容量/HA/可靠性仍NO_GO。
