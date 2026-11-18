# M05 guard 修复：被动导入与实际能力分开

G `b78a28d62b334c63ef0598f95073823dbd9b7781`（tree `0a43f607532465e86cae923a082d0af5dbc7c921`）的一次获准 pure stub/AST 已首轮退出 0，CPU2，monotonic 238,502,353 ns。六个所需标准库模块被动 import 可达，28 个能力负控拒于 raw sentinel 之前，sentinel calls=0、actual children=0、virtual children=0；未执行 whole 或导入产品/测试/helper。五份原件共 7,150 字节保存于 `evidence/preparations/m05-guard-stub-b78a28d/`。这仅是 stub/AST 通过。

独立 CODE 随后发现仅 patch `signal` API 仍遗漏 `_signal` 原生别名；现有目标没有该调用，但广义 signal 全拒绝断言尚未闭合。此新 finding 单列保留，不能用上面的 stub 通过覆盖它。原 G 不改、不重跑；后续 CODE 补丁必须有新 source，当前没有追加执行授权，next_run_permitted=false。

后续 alias CODE 已对 `signal` 和 `_signal` 的同一组 effectful API 同时 deny，并明确 deny `socket.socketpair` 与 `_socket.socketpair`，保持 `socket.socket` 类以供 ssl/asyncio 被动 import 使用。预检源码对应增加纯 sentinel 负控；这些新源码尚未执行，旧 28-case stub 不作为新 alias 源码通过记录。exact-six Popen 与父 SQL/UTA active guards 的 AST 仍不变；`guard-alias-source-bindings.json` 单独绑定新源码与 false policy，原 G bindings/first 证据不回写。

本修复仅改测试执行器，不改 controller、cold helper、测试、两 workflow、public recipient、业务 runtime 或 strict19 模板。原 C `4eabab3` 的首 4 PASS + 8 import ERROR / 0 child / exit1 及 ed55fc9 的全部 37,788 字节原件保持不变，仍是 FIRST_ERROR/NO_GO。

root 新授权仅覆盖新 guard CODE 和一次 CPU2、外层 10 秒以内的纯 stub/AST 预检；没有授权新 whole suite 或六个真实 child，更无 actualM05/marker/ref/push/CI/SQL/业务/worker/OpenSSL/网络。current policy 与 next_run_permitted 保持 false，独立 guard CODE 审核暂待。

修复去掉 `_scope_audit` 对 `concurrent`、`multiprocessing`、`ctypes` 等标准库名称的 import 黑名单。所需框架的 `unittest.mock → asyncio → concurrent.futures` 可做被动导入。能力限制仍在：精确六条 helper `-I -S` Popen allowlist 的完整 AST 未改；其余 Popen、底层 fork/exec、os.system、线程启动、进程启动、Executor.submit/Pool 构造、socket/SQL/native loader 的 audit、信号发送/handler/wakeup/timer API均拒绝并计数。线程和进程池模块在 source loader 返回时 patch 实际启动方法；已有模块亦处理。`Thread.start`、cached `_start_new_thread` 与 `_thread` 别名同时拒绝。stdlib `ctypes` 若在初始化中主动调用 native loader，loader 事件仍会拒绝；这按实际能力事件判断，不是名称黑名单。

父 SQL/`_sqlite3`/UTA active import Finder+audit AST 未改；子解释器原 cold helper 在目标 exec/产品 import 前安装的相同 active import guard 未改。通用 guard 同时硬拒 subprocess/raw-fork，且仅父 exact allowlist 调用期间拥有瞬时许可。后续真实 child 仍必须给出 source hash、真实六次计数、exit/reap、cold 正负控及 hard-guard 首证明，stub 不能替代。

预检通过 AST 取出 guard 与父 import guard，绝不 import runner/helper/controller/tests。先把将探测的 raw OS/process/thread/signal API 换成不可达 sentinel，再安装 guard；真实执行的只有标准库被动 imports 和 SQLite/UTA 的拒绝前 import 请求。socket/SQL/FFI 只由纯桩发出同名 audit 事件，不调用真实 API。记录必须分列 raw sentinel calls=0、actual children=0、virtual children=0，以及所有被拒 case；不把模拟计数当作真实 child 或安全沙箱证明。

任何预检首 FAIL/ERROR/UNKNOWN 原样保留，不同源重跑。即使预检成功，也仅证明该 guard 的纯桩/AST 合约，仍须独立 CODE 审核，再由 root 决定是否另授权固定新 C 的一次 whole。回滚仅回退本 harness CODE/docs，并保留全部原始证据；生产、10k/s、HA及真实资金 flags 全 false。
