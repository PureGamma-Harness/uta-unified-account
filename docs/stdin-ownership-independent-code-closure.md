# Readonly stdin 六方法闭包：独立 CODE 修复核对

固定新source `c076b0dc1feb765686de9c78683a4e4bea5429e2`、提案tip `44e298456922975529a4e7d194e0c964b9f3d01b`。**STDIN-CODE-01按CODE关闭，六方法仍NOT_RUN。** 原9596未执行、c9实际首FAIL与cabb原静态finding的历史范围不变。

新AbsoluteMemoryPath继承PurePosixPath，仅对已经absolute的词法路径返回self；遇相对路径明确拒绝。第6方法的实际audit现在注入这个fake，execute内MemoryPath也继承它，因此目标.absolute()调用具有所需接口，不会以此前AttributeError替代write-guard拒绝。该补充没有实际路径查询、设备打开或文件写入。

probe SHA `4624f4cd5181d5ef526f60cb6c2b126421eace16741537d7a021775397a12bcc`在9596、新source和提案tip完全相同；新test SHA为 `65508ce14d0cab5667ceb7d8a3551627694748676adf25de459d20a34795a443`，六方法数量不变。readonly FD、精确stdin替换、write audit、stdout read1和部分constructor清理都未为修fake而改变。c9首次实际FAIL的9个新增文件在新tip仍逐字节保留。

其余范围沿用前次CODE限定：未知birth/构造失败不会变scope PASS，合作2s窗口不是硬实时I/O保证，actualDEVNULL原分支未因FD替换而获得验证。当前没有新增确定阻塞妨碍root考虑新source的唯一六方法纯批次：CPU1/10s、最多32小fake分支、原始合计输出≤100KiB，fixture不得实际打开null、创建child/pipe、写FS、使用SQL、网络、信号或旧数据。

这只是可单独提审的纯验证范围，**不是执行GO或PASS**。actualonce02仍须后续独立具体授权；不得在旧dc1e/c9路径重跑或修改原首FAIL。来源与AST记录见 [静态闭合](../evidence/reviews/stdin-ownership-code-closure/static-code-closure.json)。

本OWN仅新增独立文档与静态记录，未运行任何新旧测试/native/SQL或更改候选。回滚移除本OWN新文件并保留原finding与全部首次证据。生产、容量及长测资格仍为NO_GO。
