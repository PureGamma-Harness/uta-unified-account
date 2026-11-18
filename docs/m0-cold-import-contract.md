# M0 cold-import 合约：隔离全测试进程的合法缓存

固定首CI证据OWN `dc9e42ababfd29106129d85ecd00ae4c38ebbb8c` 记录 generalCI44199787800/source e643661：四个runtime各1959tests，3.10/3.12/3.13各2FAIL，3.11另有5秒native恢复horizon失败，所有package步骤NOT_RUN。两个共同失败是escrow:108与integrity:141的全process sys.modules断言；不能归因为被测模块实际引入SQL，也不能改写旧CI为PASS。本修复没有重跑CI、下载ZIP或执行package/native/H1AuthDB。

## 实现与作用域

新test-only工具tools/cold_import_contract.py用当前sys.executable启动 `-I -S -c` 新解释器。删除传递环境中的PYTHON*变量，cwd是独立private目录；-I忽略PYTHONPATH/user site，-S关闭site/sitecustomize自动加载。父进程合法缓存与真实业务测试可以继续存在，不清空共享sys.modules，不用before/after差集冒充导入边界。

在目标代码执行前，child安装audit import hook和首位meta_path finder，主动拒绝sqlite3、_sqlite3、uta及其子模块。先检查child无这些缓存，再加载两个实际已审source文件的精确bytes并compile/exec为非__main__模块；源SHA与父预期闭合。加载结束还拒绝任何blocked cache注入。负控调用__import__('sqlite3')、__import__('_sqlite3')和__import__('uta')，只接受本guard的ForbiddenImport，不能以ModuleNotFoundError或最终cache空作为成功依据。未真实载入SQLite/UTA模块或打开DB。

原controller与m0_stream_escrow文件字节均不变。仅两项测试从全process缓存断言改为调用该probe；其no-SQL/product要求保留并加强。两个M0 workflow仅增加新helper与窄test的sparse路径，source checkout/action/ref、namespace04、预算、argv及marker都不变，不创建M05。一般CI完整checkout也可获得这些文件。新test文件沿用test_independent_m0_*命名，以便同一已有发现规则纳入。

这是可信source的导入契约，不是任意敌对Python代码sandbox、网络隔离、所有未来function路径无SQL证明或stdlib/动态链接器供应链证明。检查canonical import roots和cache，不声称阻止任意alias/dlopen路径。-I/-S与当前固定source共同限定了本次证明范围。

## 有界进程、错误和raw

每个child申请1秒执行预算，超时只对直接Popen拥有的child kill，并最多一次1秒wait/reap；无法reap明确CHILD_REAP_UNKNOWN，不造完成证明。4个真实child的程序预算不超过8秒，整个唯一batch另有GNU timeout10秒。OS停顿、阻塞IO与kill本身不具物理实时保证；该测试infra不是金融owner或DR控制器。

child输出文件有32KiB RLIMIT_FSIZE，父只接受单一严格JSON proof、预期mode/flags/版本/guard事件/源hash，stderr非空、非零exit或malformed均UNKNOWN。父结果只含固定code、闭合流length/SHA及通过精确验证的proof，不回显exception str/repr、命令行或raw路径内容。私有文件0600、目录0700；正常测试临时目录随scope清理，首授权batch另保留全部原始closed streams。cleanup syscall失败可导致UNKNOWN，不承诺强制成功或磁盘quota。

## 首批实际结果与限制

本机一次CPU2、`-I -S -B`、10秒outer batch，8methods PASS，0failures/errors/skips，294614682ns。恰好4次真实子解释器spawn：controller与escrow在父合成sqlite3/_sqlite3/uta缓存及poison PYTHONPATH/PYTHONHOME下均PASS；两个负控各PASS，sqlite负控同时验证_sqlite3。4真实child正常exit并reaped，没有真实kill；guard事件证明负控在加载前拒绝，blocked cache count均0。

该唯一批后静态发现parent wait OSError再reap0可能覆盖首技术错误；最终CODE仅收紧为code必须等于CHILD_EXITED才能接受proof，其余状态始终UNKNOWN。child程序及两个真实target字节不变；首批helper/test源码snapshot与原8结果保存。新增第9项纯桩负控供独立CODE审验证，**本作者未再跑它或重复真实child/CPU2批**，不能把8PASS标作最终9项已运行。post-batch-tightening.json精确列出该局限与变更。

timeout kill/reap、reap未知、spawn异常、malformed输出、missing source只用纯桩或临时文件，UNKNOWN是这些测试**预期结果**，并非真实child失败。16份closed stdout/stderr全在外部首私有目录保留，Git保存全部父首stdout/stderr、sourcepins、case_results与四个真实child严格安全JSON原字节。异常桩raw仅保私有及哈希，不声称已完整公开raw。首stdout的all_expected_child_proofs字段实际误名为按unittest字母序收集的前四case状态，包含预期stub UNKNOWN；保留首字节，不以该摘要代替完整按tag的四个真实proof。static-scope.json给出明确解释。

源和首raw在evidence/reviews/m0-cold-import-contract。此批没有执行原1959测试全suite，也没有证明四个CI Python版本全部通过；3.11 native恢复、独立router新RED、manifest选择及所有真实交易/容量门槛仍分别待审。不产生M05或生产GO。

## 评审、后续验证与回滚

独立组核固定code/sourcehash、guard先于目标执行、负控真实被guard阻断、父缓存污染、-I/-S/过滤环境、sourcebytes不变、timeout/直接child reap和无raw泄露，审查两workflow确实只补测试依赖。本轮小解释器是root明确授权范围，不能解释为允许一般SQL/native测试。

未来新source的窄复测可用 `timeout --kill-after=1s 10s taskset -c 2 python3 -I -S -B -m unittest discover -s tests -p 'test_independent_m0_cold_import.py' -v` 保存**新**输出；不要重用run_first_pure.py的O_EXCL首私有目录或覆盖首结果。一般CI、构建和native恢复复测由root在具体审查后分别安排，不rerun旧首失败。未来4runtime的原unit日志、源码映射及package状态都重新按新SHA验收。

没有数据/schema/账户迁移或服务部署。回滚仅撤回test-helper/test/workflow依赖变更并保留全部首原件；原两个全进程断言恢复后仍是已知CI NO_GO，不能删除no-SQL要求来获得绿灯。旧M04/1d727/controller/业务source909及正在运行作业完全不改。
