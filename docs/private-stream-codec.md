# 私有事件流纯 codec 原型

状态：**COMPONENT ONLY / NO LISTENER / NOT PRODUCTION QUALIFIED**。
本切片从固定M2 `a35fd56`、设计 `c68aabe` 与追加修订 `5348ab3` 开始。独立设计审查
`f7a86b5` 与V2闭合 `9bf26dd` 没有替代运行时代码审查。本实现只新增
`uta/private_stream_codec.py` 和pure tests；现有gateway、auth、view、financial、observer
模块没有变化，也没有服务import这个新模块或新增入口。没有SQL、socket、listener、
nonce/session binding、bounded reader或资金行为。

## 实现范围

- `validate_handshake_key` 只核规范16byte Base64 key、signed hex challenge的一一绑定及
  RFC accept算术。`HandshakeReject` 是HTTP400，不冒充HMAC/nonce/权限验收。
- `FrameParser` 只接收masked客户端control frame，每次最多完成8个，未消费输入通过
  `consumed` 留给调用者。内部header/payload scratch≤139bytes，不收客户端data body。
  RSV/opcode/mask/最短长度/63bit上限/control FIN与125byte上限先检查；合法fragmented
  text属应用拒绝1008，非法continuation/control为1002。close reason精确UTF-8校验，
  close code使用设计V2固定集合。客户端1010有效，但建议回包1000，服务器不生成1010。
- 首字节起header500ms、完整frame1000ms是绝对模型期限；传入时间回退给出1011。
  `PingTracker`只匹配唯一未决payload，unsolicited/不匹配pong不清期限。
- `WireFrame`将header和不可变payload分开，输出队列不拼接整个大frame。公共view的
  backing也不可变；`to_bytes()`明确产生最多256KiB的副本，仅供小向量或受控调用。
  text payload≤262134bytes，加10byte header后whole wire≤262144。增量chunk在复制前
  计长并验证UTF-8，最多65536chunks以拒绝无界空chunk迭代。
- `OutboundBuffer`按完整wire会计：application最多2帧/524288bytes，control独立2帧/
  254bytes；partial write期间保守保留整帧计数。`peek/advance`只接受最近发出的同一
  `SendChunk`对象和offset，拒绝伪造/过期凭证跳过bytes。control可优先，但不能插进
  已开始frame。close清掉未开始的page不表示客户已应用；已有frame只能在原500ms内
  完成或由调用者abort。进入closing即开始2000ms总期限；最老未送application达5000ms
  触发4008。所有这些是显式调用驱动的模型，不是一个实际reactor。

调用者在frame开始发送前仍负责真实auth检查；拿到`SendChunk`不等于有数据发送权限。
返回的错误与`abort_transport`也需要未来listener实际执行。库不会执行socket操作或
在错误后替调用者发送close，更不会推进任何客户业务cursor。

## 容量及下一层边界

`enqueue_text_chunks`先检查队列容量，再向上游请求第一个chunk；满队列时不消费数据源。
独立`encode_text_chunks`只能限制它自己接收后的复制，不能撤回上游已分配的对象。
`JSONEncoder.iterencode()`本身可能一次分配巨大string chunk，所以本纯bytes库不能证明
上游JSON分配有界。下一serializer需要逐字段字节前检/有界字符串分段，且只在队列有空位
时构建。冻结不可变payload时的临时bytearray、UTF-8验证str、TLS/kernel buffer和Python
对象也不由wire队列字节计数证明；RSS与真实调度全部未测，不把逻辑上限改写成heap证明。

下一bounded reader还必须保留byte-cut prefix后的真正cursor。例如after400、H450，407/
413两行各64KiB已达128KiB页预算，420另有1byte：只返回两行时必须has_more=true、
next_after=413；不能调用原`_page(limit32)`因为两行少于32就误记has_more=false、前进H。
这项SQL/reader用例在本库没有实现或执行，不是现有pure tests的通过项。

## 测试与证据口径

测试用原10个control字节向量、独立review追加5个close/header向量、V2 canonical Base64
别名与whole-wire边界、全部两frame输入切分点、逐byte UTF-8/掩码偏移、partial output/
close不交错和deadline模型。样本来自原30+V2手工fixture，但不表示其中权限、nonce、同RO
snapshot、网络时延等其余要求已通过。客户端大整数只验证bytes未经过float，不代表SDK
正确应用了事件。原测试缺实现的ImportError和开发中实际FAIL/ERROR均保留原source/hash。

实际固定源三运行时小suite、原始日志、source SHA与运行环境将单独归档，之后由另一组
只读审查。没有完整repo、CI、wheel/sdist、installed、长稳、网络、压力或生产资格转移。
M2及两个原长作业的源码/运行数据未访问或修改。

## 部署与回滚

这是默认无人调用的纯库，不部署listener或迁移数据。实验使用独立合成工作树和模型时钟，
不改系统clock、lease或行情时间。回滚只移除新增模块/tests/docs；没有账户、资金、
nonce、游标、authority或worker需要回滚。若以后并入发布，新增源码会改变artifact身份，
必须按新固定SHA重新走全量/CI/包/独立审查，不借M2 PASS或原六/24小时作业宣称合格。
