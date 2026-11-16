# 验收记录器的实际故障与修复

历史全量 793 项结果仍保留原文件。旧记录器仅用 Python stream
redirect，spawn 子进程继承的实际 fd2 未全部归档；它不改变 unittest
的真实通过计数，但原日志不能宣称包括所有子进程原始 stderr。

新记录器在独立 worker 运行同一源码测试，以 OS stdout/stderr 合并至
原始日志，保留真实退出码、实际测试计数、代码前后摘要、tracked source
是否干净。测试通过但源码被修改或未提交时，整体 `passed` 为 false。
不会根据日志中的成功字符串或历史测试数推导通过。

本目录记录 5 项最小独立 Git fixture 的真实执行：OS 级子进程 stderr、
真实断言失败、执行中改源码、未提交源码、测试发现失败。首次一个 fixture
把子进程字符串中的 newline 多层转义错了，导致真实 SyntaxError，原失败
日志保留；修正 fixture 后 Python 3.10/3.12 各 5 项通过，没有跳过或改弱
金融预期。完整候选随后从冻结 commit 再执行。
