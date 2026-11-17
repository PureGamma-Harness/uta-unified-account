# 私有事件流 V2 修订：读取、握手与调度边界

状态：**DESIGN / NOT IMPLEMENTED / NO-GO**。本修订追加于
`c68aabe82ce78ab10a3c886894ce8dc9952302d1`，原设计、原30个人工案例及其静态证据的
字节均保留。它回应独立审查 `f7a86b5a7a53476fb277272b0d5cb7c679d73540` 的 WS-R1–R5。
有冲突时本修订优先；这不把旧要求改记成通过，也不授权 listener、SQL 或资金代码。

## R1：先核实际 UTF-8 字节，再取任何正文

原文把现 REST `_object` 的 `4*1024*1024` 当作MiB字节是不准确的：实际条件是
`len(value)`，单位为Python字符。新WS不能以此证明任何UTF-8字节容量。ASCII包装
`{"x":"..."}` 加2,000,000个“汉”是2,000,008字符、6,000,008 UTF-8字节；4,194,304字符
的理论UTF-8上界可达16,777,216字节。这是纯字节算术，不是SQL或内存压力实测。

新 `_stream_context/start/page` 必须先在同一短 **RO事务/连接** 中取得 exact identity、
类型、数量和 `LENGTH(CAST(column AS BLOB))`，在通过前不把对应TEXT/BLOB正文取到
Python，不调用JSON/MarketSnapshot解码，也不调用现有未经该前检的 `_context()`。
先前另一次transaction的COUNT/LENGTH不能为后一次payload读取背书。SQLite自身为
计算长度可能产生I/O/分配；这只限制Python物化前的门槛，不是SQLite/OS/RSS硬上界。

| 来源/依赖 | 单行UTF-8正文预算 | 同一事务内额外边界 |
| --- | ---: | --- |
| `uta_config` 的 `policy`、`risk_policy` | 各32,768字节 | 两项合计65,536；只允许指定keys和TEXT；halted只允许原true/false且≤5bytes |
| `uta_market.payload` 当前行情 | 262,144字节 | singleton/type/行数核验；缺报价保持missing，损坏或超限拒绝 |
| 当前行情引用的 `uta_market_history.payload` | 262,144字节 | 在读archive正文前单独LENGTH前检，核同SID、原内容及digest；不能只检查current |
| schema/authority/shard/config identity、guard SQL等文本依赖 | 每单项≤16,384字节 | 此类metadata合计32,768；行数/唯一项/typed值限制先行；官方保护缺失或超限均拒绝，不跳过校验 |
| snapshot基础账户资产/负债文本 | 单项资产ID≤128字节、金额文本≤512字节 | assets/liabilities各≤256；抓取前核类型/字节/行数，仍核精确scale与gross debt |
| `uta_events.payload` | 65,536字节 | 账户先过滤、按序选择≤32行，原payload合计≤131,072；不得跳过首个超限事件 |
| event_type/created_at/account等事件文本 | 每项≤128字节 | 类型/列identity核验先行；cursor与sequence必须相等 |

一次context的被选文本预算合计≤655,360字节，且仍受各项上限；累计长度在读取正文前
求和并检查有界整数。只选择当前行情的相关archive，不读全历史。基础快照受整帧编码
上限约束；不能把counts限制当成字符串或编码字节上限。引用audit/schema保护的内部
校验也必须审查其完整TEXT依赖；不能先调用一个无界validator后声称上述前检覆盖全部。
如现有共享函数无法接收经本事务核验的有界原值，则先建立独立bounded helper再复用纯
验证，不在本片假定“当前 `_context` 已安全”。REST原有上限与行为不因新WS而改变。

查询形状是先选固定key/singleton下的 `typeof(...)` 与上述BLOB长度，再取确切主键/
sequence的原值；**这些是拟定SQL契约，本提交没有执行SQL**。每一步保持同一SQLite
snapshot，防止两阶段之间换正文。超限、非TEXT、异常UTF-8、数据/引用不一致、长度或
读取不可用，均无账户frame、无cursor推进；按原503或已连接1011处理。单事件过大按
1009且不跳过；先前合法prefix可发送后在下一范围停于该事件。不存在吞掉坏行的fallback。

## R2：规范 Base64 使 challenge 唯一绑定原 key 文本

Python `b64decode(validate=True)` 不是规范编码检验。RFC例子
`dGhlIHNhbXBsZSBub25jZQ==` 与末尾pad bits非零的
`dGhlIHNhbXBsZSBub25jZR==` 都能解为相同16字节，因而产生相同hex challenge；但用原
header文本计算的accept分别是 `s3pPLMBiTxaQ9kYGzzhZRbK+xOo=` 与
`Zgw8jYXtqX5qJr7MJ1Q/MqzeSRI=`。原设计不能仅凭decode成功宣称绑定了确切文本。

新增结构条件：key必须唯一ASCII、严格decode为16bytes，且
`base64.b64encode(decoded).decode('ascii') == original_header_value`。拒绝空白、非规范
padding、非零pad bits、重复header或别名，不能strip/规范化后接受。此条件与原
`challenge == decoded.hex()`共同构成规范key文本的一一绑定；现有HMAC仍签原始target
中的challenge，body仍为空，不另改REST签名v1。accept只由这个已验证的原规范header
计算。结构失败在nonce消费与金融读取前400 `invalid_ws_key`，没有101。

## R3：有方向的关闭码与回包

本提交读取IANA WebSocket Close Code Number Registry，URL/时间/SHA与所见记录单独
归档；运行时不得联网查表。下面为本协议版本固定的wire集合，后续注册变动须新审查。

| 范围/code | 收到客户端close | 本服务器encoder | 本listener主动使用 |
| --- | --- | --- | --- |
| 1000、1001、1002、1003、1007、1008、1009、1011 | 合法，理由须UTF-8且总payload≤125 | 合法 | 按V1场景 |
| 1010 Mandatory Extension | **客户端方向合法** | **禁止生成/echo** | 从不使用；不接受extensions不使客户端的合法close变成坏帧 |
| IANA已登记1012、1013、1014 | wire合法 | wire合法 | 首片不主动使用，不能冒称重启/代理行为；原slow_consumer仍4008 |
| IANA已登记3000、3003、3008 | wire合法 | wire合法 | 首片不主动使用 |
| 4000..4999 private use | wire合法，即使本应用未定义其意思 | wire合法 | 主动只用4000/4008，不解释对方未知private code为资金指令 |
| 1004、1005、1006、1015 | 非法上线路，1002 | 拒绝编码 | 只能将1005/1006/1015作内部观测标签，不能塞wire |
| <1000、≥5000、1016..2999、其余当前未登记3000..3999 | 本固定profile拒绝，1002 | 拒绝编码 | 不使用；不是以1000≤code<5000代替完整集合 |

收到**任何合法客户端close**，本listener停止新的application frame，正常回应1000、空
reason；不盲目echo code或reason，因此客户端1010不会被服务器重发，用户文字也不进日志。
零字节close payload合法，也回应1000；一字节payload非法1002；有code时reason必须合法
UTF-8，否则1007。其他RFC协议错误先于“不支持客户端业务data”的应用拒绝：RSV/mask/
最短长度/64bit高位/fragmented control/无message的continuation错误为1002；合法但本
应用不接受的fragmented text为1008。此前有限frame例保留，不能称完整codec验证。

## R4：绝对期限与不被半帧阻塞的调度

listener必须使用nonblocking TLS/socket和增量状态机；reactor不做阻塞式read-exact、
sendall、SQLite查询或任意JSON解析。对SSLWantRead/WantWrite登记所需interest，按最早
deadline等待，不因一次recv获得了一个字节就重置总期限。每个调度turn优先处理已经到期
的授权/心跳/close/输入期限，再处理有限数量可读写工作；不能因某个socket一直ready饿死
其他连接。单连接每turn最多8个control frame/64KiB I/O，超过留待后轮；control速率桶保留。

| 阶段 | deadline起点与绝对预算 | 到期行为 |
| --- | --- | --- |
| TLS+HTTP握手 | accept时刻起总3,000ms | 不被任一字节/SSL往返延长；关闭或有条件发送408，无101 |
| WS header（2byte base+所需ext length+mask） | 本frame首字节起500ms | incomplete则1008 `frame_read_timeout`；不取下一frame刷新起点 |
| WS control完整frame | 同一首字节起1,000ms，包含header时间 | 半payload进度不延期；1008且保留业务cursor |
| auth schedule/结果 | 各session每250ms到期；本次请求结果预算100ms | 结果缺失禁止新账户frame，1011 `auth_check_timeout`；不继续用旧principal |
| ping/pong | server ping开始发送时固定10,000ms | 只有匹配pong清除；不匹配/unsolicited pong与半帧进度均不延长；超时1001 |
| 每个出站frame | 首字节尝试发送起总500ms | 不因partial write延期；不能完成则abort transport，不把close插进半个frame |
| close/drain | 进入closing起2,000ms正常目标 | 不等不相关frame或后台工作再开始计时；截止关闭自有socket |

无首字节时没有凭空的header期限，idle心跳和auth期限仍生效。parser只分阶段读取当前
header所缺字节，再读取最多125bytes control payload；最多14byte header+125byte parser
scratch，禁止按客户端声称的大data长度分配。TLS内部record buffer不由139byte scratch
预算证明；它仍计入进程资源验收。过大的/不允许的data在header检查后关闭，不排队其body。

SQLite即使设置timeout/progress也可能阻塞OS I/O。为维持reactor进度，拟定auth-recheck
独立有界lane（1个worker、总in-flight+queued≤8）与data-reader lane（2个worker、总in-flight+queued≤8），
每连接每lane最多一个in-flight，不在reactor等待future。两lane不共享连接/事务；线程
只打开自己拥有的已有mode=ro连接。超时结果丢弃，不复用来授权，也不创建替补线程或
无界重试队列；lane不响应则listener降级、停止新连接并关闭受影响session。进程隔离是
必要前提；若OS I/O阻塞使worker无法退出，由只针对stream进程的外部supervisor处置。
本提交不把该目标写成已测hard RTO，也不以它终止writer/auth服务或任何现有长作业。

每个application frame首字节前仍需精确session binding检查，成功结果age≤100ms；每250ms
是空闲检查频率，不是允许旧授权250ms后再发frame。若data结果回来时授权已过期，先等
本次fresh检查，不能边发边补验。已观察撤销时清除未开始的application队列，不推进客户端
cursor。已经开始的frame不能与close interleave：只能在原发送期限内完成或中断transport，
随后不再开始任何application frame。此竞态和已进内核bytes不可撤回的限制仍保留。

## R5：整帧字节与队列会计

V1的256KiB明确为 **whole wire frame**，512KiB为待发送application整帧队列，均包含RFC
header，不只JSON body。server不mask：payload≤125时header2bytes，126..65,535时4bytes，
≥65,536时10bytes。因此大JSON UTF-8 payload最大为**262,134bytes**，加10恰为262,144；
262,135加10超限一字节。源event≤65,536、page原payload总和≤131,072仍是独立的输入门。

编码必须增量计数并在超限前停止；不能先 `json.dumps()` 无界大字符串再拒绝。队列最多2
个application frame，wire总和≤524,288，部分发送仍保守计入原完整frame直到对象释放；
另一个正在构建/等待授权的frame也≤262,144。因此这三类wire buffer合计≤786,432bytes。
控制输出另有最多2帧、总254bytes的优先预留（每帧2+125），不能被满application queue
饿死。多个未回应ping可依RFC只保留最新pong；关闭时可丢弃未开始的application和过时pong，为close保留槽；不能因此标记页已被
客户应用，且继续传输期间不能跳过事件。TLS/kernel buffers、Python对象/JSON/SQLite heap
不在此wire计数内，**786,686bytes不是RSS证明**；256MiB进程上限和实际峰值仍需独立实测。

## 追加案例、证据和后续批准

新增fixture与static checker位于
`tests/fixtures/managed_private_stream_v2_contract.json` 和
`docs/evidence/private-stream-contract-v2`。只计算UTF-8/Base64/SHA/整数/header长度及有限
时间轴，不执行SQL、socket、认证、buffer、codec或listener。原30项仍是NOT_RUN_REQUIREMENT。
本V2也没有将权限、nonce、同RO snapshot、撤销或调度目标记为通过。

纯codec/有界encoder先行仍需root单独GO。auth会话receipt/只读重检、bounded context reader、
最终default-off TLS listener分别审查；不能以V2文字关闭代码验收门。部署/回滚和原权限/
资金边界仍按V1，仅在新合成环境使用，原M2 frozen、observer及livejob保持独立不变。
