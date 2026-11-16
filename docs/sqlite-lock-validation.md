# SQLite 主文件锁所有权独立验收

本轮只新增 `tests/test_sqlite_lock_ownership.py` 和本报告，不修改 runtime、root 工作树、
实际 24 小时任务目录或其数据库。全部用例只使用本地临时合成数据库。生产保持 **NO-GO**。

## 来源和固定红态

红基线为 `57d776ced8d9b304b651925d8c13f5e7e7ad6272`，独立工作树为
`/workspace/uta-lock-faults`，分支 `test/sqlite-lock-faults`。

第一手说明为 SQLite 官方 [How To Corrupt An SQLite Database File，2.2](https://sqlite.org/howtocorrupt.html#posix_close_bug)。
官方指出，同一进程中任何线程对同一文件执行 `close()`，可能取消该进程其他描述符持有的
POSIX advisory locks；SQLite 自己管理多个连接时会规避这个问题，直接绕开 SQLite
打开再关闭数据库文件则破坏其锁状态。SQLite 3.51.0 后新增 WAL 防御也不是完整替代。
本轮读取的原始 HTML 为 `/tmp/uta-sqlite-official-corruption.html`，SHA256：
`e00709e3f37e95332d8e6df243510665e9cab1d7938d4fd85cbf5f47648a50bf`。

旧 `Database`、`_BoundShardDatabase` 和 `_ExistingAuthDatabase` 的文件检查都会在每次
连接前直接 `os.open`、`fstat`、`os.close` 已发布的 main DB inode。独立测试没有复用
实现组的 probe，也不以 SQLite 的进程内缓存状态作为 kernel 锁证明。

## 独立锁协议

进程 A 是测试解释器，使用正常 `Database` API 保持真实 SQLite 读或写事务，并执行实际
SELECT；写事务还完成尚未提交的 UPDATE。先由独立进程 B 证实 SQLite 的 Unix 主文件
SHARED 字节范围仍被锁定，然后让 A 的第二线程仅执行正常文件检查、第二个只读事务或
一次应超时的写事务。A 的原事务必须仍 active，B 也必须仍无法获得该范围的排他锁。
原连接关闭后，B 才应能获得锁，避免把其他残余持有者误认为测试成功。

B 每次都是新 PID，只使用标准库 `fcntl.lockf` 非阻塞探测 SQLite Unix 主文件的
`SHARED_FIRST=0x40000002`、`SHARED_SIZE=510`。它不创建 SQLite 连接，不读取本进程
SQLite 锁缓存，也不修改数据库字节。被测数据库为该应用实际使用的 WAL 和默认 Unix
VFS；每次探测前必须先验证真实 SQLite 基线锁确实阻塞 B，没有用 skip 掩盖环境差异。

另一个独立 B 用正常 SQLite `BEGIN IMMEDIATE` 和 UPDATE 验证 A 写事务未释放时仍 busy，
释放后才可提交。WAL 的其他锁可能继续阻止某些 SQL 写入，因此“B 的 SQL 仍 busy”不能
推翻“主文件 kernel 锁已经丢失”的直接证据。

## 八项独立用例

| 用例后缀 | 验收 |
| --- | --- |
| `private_checks_cannot_release_another_threads_actual_sqlite_read_or_write_locks` | 三种数据库类型分别保持真实读、写事务；同 PID 第二线程仅执行 `_private_file` 后，独立 B 仍不能取得主文件排他范围。 |
| `normal_second_read_transaction_cannot_release_a_live_main_file_lock` | 第二线程使用普通只读事务并关闭自己的 SQLite 连接，不能释放 A 的主文件锁。 |
| `rejected_second_writer_preserves_existing_kernel_lock_and_holder_commit` | 第二线程写事务真正超时，A 的 kernel 锁和后续原提交仍必须正确。 |
| `separate_pid_sqlite_writer_stays_busy_until_original_writer_releases` | 独立 B 的实际 SQLite 写入在 A 释放前拒绝，释放后提交一次；原 counter 最终精确为 101。 |
| `existing_public_or_symlink_database_is_rejected_without_modifying_its_bytes` | 现有 public 文件和符号链接路径都拒绝，真实 main DB 字节 SHA256 不变。字节读取仅在没有活动连接的用例中进行。 |
| `missing_read_only_targets_never_create_main_database_or_sidecars` | 普通、auth-existing、shard 的缺失只读路径都不得创建 main 文件或 sidecar，也不能进入调用方 body。 |
| `shard_identity_and_managed_writer_fencing_remain_mandatory` | 错放真实有效分片文件仍拒绝身份；managed 普通无 token 写入仍拒绝，合法 token 存款和 ledger.verify 可继续。 |
| `bounded_concurrent_dml_and_ddl_conserve_balances_and_reopen_cleanly` | 两线程与独立 PID 通过正常事务处理 36 笔唯一合成转账及 12 张实际 DDL 表，现金总额保持 2000；重开 integrity_check 为 ok，main/WAL/SHM 类型与权限正确，无意外 sidecar。 |

并发用例是有界正确性检查，不是容量、尾延迟或长稳测试。auth-existing 用例验证其真实
文件预检查类，不冒称完成认证协议或 nonce 吞吐验收。受限 shard 和 writer fencing 的
原权限边界不因文件检查修复而降低。

## 红态实际结果

```sh
python -m unittest discover -s tests -p test_sqlite_lock_ownership.py -v
```

```text
Python 3.12 / SQLite 3.53.1: Ran 8 tests in 1.730s — FAILED (failures=16)
```

16 为 unittest 子用例失败数。三条文件检查路径都检出了 active SQLite 事务仍存在、
但 B 的 kernel 排他探测从阻塞变为可获得；普通只读缺失路径还实际创建了空库。
正常 SQL busy、合成 DML/DDL、权限和身份的正向用例仍通过，没有据此掩盖主锁缺口。

独立测试文件冻结前 SHA256 为
`8d1cbff2b857e91fc907e5f327ba49a9446ab0c59866005e10fda447212c1cda`。
完整原始日志：

- `/tmp/uta-sqlite-locks-57d776c-red-first.txt`，SHA256
  `1490236ff794ca1b4d41b08cc4f080f273fb4544b0f3fd32c0d4092f4b49ffad`。
- `/tmp/uta-sqlite-locks-57d776c-red-py310.txt`：同一文件的 Python 3.10 独立红态复跑。

## 修复复测与部署边界

实现组已提供独立候选 `dabbeeb`，计划对现有文件仅作不打开描述符的路径检查；新建文件
只在未发布 inode 上先关闭描述符再原子发布，并禁止校验后缺失路径被 SQLite 自动创建。
本组会在保留原锁、权限与 fencing 断言下摘入候选复测，完成后补充确切结果。

本轮没有部署或数据修复动作。旧版本已完成的压力测试不能自动成为修复候选的容量或恢复
证据；仍需在新的冻结版本复跑相应门槛。恢复和回滚不能通过关闭锁、放宽文件权限、接受
缺失分片或删除 managed guard 来绕过故障。

本次证据覆盖 Linux/POSIX、被测 SQLite Unix VFS、本地 WAL/FULL 的具体路径；不证明
任意网络文件系统、硬件断电、复制共识或跨节点 fencing。没有构造破坏数据的锁协议工具，
也没有尝试利用已丢失的锁强制执行越权写入。
