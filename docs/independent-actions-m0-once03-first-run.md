# M03首次实际run：B与留存worker均UNKNOWN，P未运行

实际marker `dfd62ae6fbbdad51b5e1b3507318b343cdc314b5` 唯一parent为39151b7，唯一diff为新增批准marker。首次run [44179679904](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44179679904)、attempt1、job134380324144于21:25:34创建、21:25:59记录failure。源码checkout、Python设置、pure控制均success；execute失败，随后public manifest核验和安全artifact上传success。没有rerun、重建分支或补跑P。

case B complete_outer=1,811,314,430ns，owner2621/birth9112被资源health gate主动TERM(-15)，leader回收，原状态UNKNOWN。原reason只有 `resource_missing_non_aux`，**没有记录具体消失路径**。不能事后将router WAL/SHM、临时数据库发布文件或其它候选写成已证明根因。public报告没有actual_driver_pid，空stdout也不能证明driver未启动或没有SQLite初始化。

随后独立escrow worker也因同一typed code被TERM，保留不完整。artifact仅有driver.stdout、driver.stderr、case-owner.stdout三条完成密文；case-owner.stderr缺失，不假定为空、不伪造第四条。root首次独立认证解密三条可用密文均0字节，四流完整性仍false；作者没有读取actualroot私钥、quarantine或原明文。只复制root明确允许的公开观察JSON（SHA9d1a1147d44c0b387837d00659f89d0660e7c290d9cb9dd2e36689a8d12356d1）。P原状态NOT_RUN，不能由组件测试或空流改为执行通过。

原ZIP artifact14372555228为227,466字节、CRC通过，实际SHA256与provider digest同为 `c0ec825e3007b902706b029efed7c3c4e103ded3ebc64c4cd0b2121a3cb7d1a1`。10个public records及manifest逐字节核验，三条cipher均符合strict CMS结构；source-manifest字节与独立核过5518 Git输入的M02相同。Git只封原8份公开JSON、provider安全字段/步骤、原cipher哈希清单与root公开观察；原ZIP、66625字节connector-decoded UTF8 joblog（SHA5d41442225e682fe6f2792117ed46a8ded7552cf773eec797fa8504e1f986c55）、binary CMS、临时下载链接继续私有，不将decoded log称raw provider ZIP。

证据目录：`evidence/reviews/independent-actions-m0-once03-first-run`。此次只provider读取、文件保全和安全核验，不重新下载原件、不运行SQL/native/crypto、不改controller/source或原M01/M02/M03。没有04登记或负载授权。所有生产、10k容量、HA和可靠性放行false/NO_GO。下一步只能先审实际文件生命周期清单与独立安全诊断方案；不能跳过资源门槛来获得完整留存。
