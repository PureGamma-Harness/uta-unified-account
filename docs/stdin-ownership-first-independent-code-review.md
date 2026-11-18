# Readonly stdin 与部分构造：独立 CODE 审查

固定候选source `9596eee193b9c75776f341a4e58126864a30d797`、提案tip `5499687219cdf99eb54f194c7de45f396bea830e`。**发现一个新纯fixture闭包阻塞STDIN-CODE-01；六方法与实际once02均未运行。** 该问题属于fake接口，不能说成生产probe、read1或金融逻辑的实际失败。

## STDIN-CODE-01

新测试第6方法在198行给实际audit定义注入 `Path=PurePosixPath`，目标audit在probe221行调用 `Path(path).absolute()`。PurePosixPath没有absolute方法，因而`/dev/null O_RDWR`负控会先触发AttributeError，达不到其期望的write-guard RuntimeError。

最小修复是补齐fake path的纯词法absolute接口，或在这条只做词法路径处理的分支使用标准Path对象；不得为测试通过放宽目标外部写guard。修复须单独冻结新源码、SHA与提案。当前不能给该六方法一个“闭包完整可直接执行”的结论，本审查也未执行它们来制造新first结果。

## 其余候选 CODE 结论

readonly stdin先lstat固定/dev/null，要求Linux字符设备rdev1:3；open采用O_RDONLY/CLOEXEC/NOFOLLOW，fstat再次核type/rdev/devino与noninherit，失败只关闭刚打开的自有FD。ChildAPI只接受原精确DEVNULL stdin并替成已验证FD；stdout/stderr PIPE参数不变，真实stdout BufferedReader/read1未被包装或改回read。目录write audit仍拒绝外部O_RDWR，未新增/dev/null写豁免。

实际Popen返回后立即登记，再查询birth和包装stderr；Pipes对象在try内先分配再init，使其部分初始化字段也在finally范围。birth未知、constructor失败或process/birth不一致仍会传播原异常，不能因合作清理成功而变adapter PASS。部分构造fallback只读已登记Popen的管道、非阻塞保留有限stdout/stderr bytes，已由真实drain完成的流不再重复读取，不增加线程或发送信号。

cleanup的2s是合作循环窗口，随后还有有限thread joins、文件写入/fsync等；它不是硬实时I/O上限。release写入、fallback保存或清理本身失败时，原primary异常保持，secondary记录可能UNKNOWN，不能声称证明了完整清理。此范围主要覆盖Popen已返回后的Pipes部分构造，不声称覆盖每个CPython内部post-spawn/pre-return故障窗口。真实once02仍需独立scope和外层实际退出核对。

除STDIN-CODE-01外，当前六fake候选使用实际AST定义与fake OS/path/stream/clock、无目标模块导入；proposal为CPU1/10s、六方法、最多32小分支。这只描述修复闭包后可考虑的纯验证范围，不是执行授权或PASS证据。

## 旧实际首FAIL保留

独立核对c9首提交的全部9个新增文件在当前tip逐字节相同。原八输入before/after map与dc1e Git byte/SHA匹配；stdout250B、stderr1701B的SHA也匹配。原exit1、99,745,469ns及trace停在_get_handles/_get_devnull的目录write guard拒绝路径。

没有data-child identity、成功reap、live-before-EOF、真实backpressure、reopen或quota验收证据；缺失记录不得推成这些步骤通过。新readonly stdin替换也不验证原DEVNULL打开分支；该历史firstFAIL原样保留。绑定见 [静态记录](../evidence/reviews/stdin-ownership-first-code/static-code-findings.json)。

## 部署与回滚

本OWN仅新增独立文档与静态记录；未修改候选、未执行新6/实际once02/SQL/watch/旧数据/native操作。回滚仅移除本OWN新文件，保留旧原件与本静态finding。实际adapter、长测、生产和真实资金资格仍为NO_GO。
