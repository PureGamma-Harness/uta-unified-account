# PR57 首次 CI 采集

本提交保存首次 push 与首次 PR 的 CI 结果：**两次均为 attempt1，8个 job、200个 step 全部 success；8份原日志均记录2171项单测通过。** 这是证据采集提交，独立 RAW 审阅仍为 PENDING，不授予生产、容量或新增金融能力启用。

源码为 `d1fd381bde923dc4010977058b76e34d6162e9a9`，[PR57](https://github.com/PureGamma-Harness/uta-unified-account/pull/57) 的 base 为 `c3e937a967711cd5cae7293ac3bf63c8260d8528`。

| 首次事件 | Run | Attempt | 结果 |
| --- | --- | --- | --- |
| push | [44320885833](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44320885833) | 1 | 4/4 jobs，100/100 steps success |
| pull_request | [44320956929](https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/44320956929) | 1 | 4/4 jobs，100/100 steps success |

矩阵为Python3.10、3.11、3.12、3.13，未替换任何job、失败结果或运行attempt，没有rerun、dispatch、cancel或远端写入。最终记录没有失败step，首失败字段保留为null。

## 单测与源码身份

优先保存两份Python3.13完整unit归档。push的实际checkout为 `d1fd381`；PR的实际checkout为临时merge `6e90e86450b4cca93a398acf29ada11ef56fa201`，两者Git tree均为 `1b0c0c6000ee4c5d5bbe5520da194a6f50da37b6`。没有把provider head SHA当作PR实际checkout SHA。

两份归档均记录2171 tests、failures/errors/skipped/expected failures/unexpected successes均为0、worker exit0、tracked clean前后均为true。408项完整unit source map的前后值相同，并逐项匹配固定head的Git字节；unittest原日志的SHA、三个ZIP成员的长度和CRC均验证。两份报告的Python为3.13.18、SQLite为3.46.1。其余6个矩阵job的实际unit计数与结果也从完整原job日志提取，均为2171和0失败/错误/跳过。

固定运行源库存是66文件：65个Python文件和1个HTML，共1,456,126 bytes。显式V3测试allowlist包含历史62个Python文件及3个funding模块，与该65项Python库存一致。完整源码摘要公开在[source-inventory.json](../evidence/reviews/pr57-first-ci-safe/source-inventory.json)。采集本身没有执行目标import、编译、测试或SQL。

## 一份实际安装归档与 push 小报告

先读取provider artifact size，再下载唯一一份实际release归档：push Python3.13的artifact `14435356583`。实际ZIP为54,692,909 bytes，SHA-256为 `f773e5c3492eaab38b53e4021ed6d9f4754ea19495dc948405ec21d15e9f3b9d`，与provider digest一致，低于64MiB单归档预算。

| 归档内对象 | 实际大小 | SHA-256 |
| --- | --- | --- |
| wheel | 394,300 bytes | `a61d2bbb1c5a466be78590fb67ca5f9632168ab849aff463ed934afacad965b8` |
| sdist | 54,542,488 bytes | `66dca1e8fdb715a038c54bb90737807116a3572e85e8432a62f68f20e4e66532` |

本地只做归档数据读取，没有extract、安装或运行包内代码。wheel的66项runtime、RECORD、metadata版本、三个console入口声明及成员CRC均匹配。sdist流式读取8997个成员，7811个跟踪文件的size及Git blob身份完全匹配，总源字节223,620,032；其中66项runtime另比对SHA-256。生成的metadata为643,382 bytes，低于固定4MiB预算。重复、额外、绝对、`..`路径及超size在成员内容读取前拒绝；读取每项受固定Git size+1限制。没有把整个sdist读进内存或落盘解包。

首次collector的expanded计数有明确口径缺口：224,263,414 bytes只计算tar成员内容；outer ZIP实际为DEFLATED，另外输出wheel容器394,300 bytes和sdist容器54,542,488 bytes。因此仅这两层累计已至少279,200,202 bytes，尚未计wheel内部和tar header/padding。原“全层累计expanded”门槛为 **NOT_PROVEN / original scope ambiguous**，不能用成员payload计数声称满足。原字节摘要、CRC和Git比对事实保留。root随后为独立组未来读取单独定义了分层预算；该新许可不追溯补签首次collector，本提交不再读取归档。

另保存push Python3.13的小package验证归档，其19成员CRC通过。原CI报告记录installed CLI tests为8/8、8条安装后命令均exit0、25个已加载模块路径归属安装site。归档manifest和installed report中记录的wheel/sdist大小与SHA都与上述实际下载字节相同。报告的66项runtime完整hash map也匹配固定Git与实际包。

这25个direct-installed模块不包含 `uta.funding_local`、`uta.funding_obligations`、`uta.perpetual_funding` 或 `uta.cross_decimal_kernel`；独立oracle `tests/pm_independent_next_oracle.py`也没有此安装路径执行证据。上述五项的 **direct-installed专项功能覆盖均为NOT_VERIFIED**。funding三模块和candidate的wheel/sdist字节身份成立，oracle源文件的sdist身份成立；这些新覆盖不补成安装后专项执行。

归档字节身份与CI记录的功能覆盖分别保留。采集者没有在本机复跑安装测试，不把包字节一致外推成交易所生产验收。

## 原件、预算与公开边界

私有原件共50文件、75,823,470 bytes，低于128MiB/256files；文件0400、目录0500。完整provider响应、全部8份job日志、首次快照、两unit归档、小package归档和唯一实际release归档均保留。FileService引用及下载URL仅留私有原件，公开文件不包含签名URL、runner私有位置、运行身份或完整原始日志。

完整index为8,473 bytes，SHA-256 `47bb3b19b895e58765e88c1ee86d3b308cc011968b999c7e8b094a7335387f0c`；seal为369 bytes，SHA-256 `32ccb8fea9c1835bc21b6457ab046145dc1f4d8f0d7ad492b967c2e8ccaf8d80`。公开匿名库存保留原件序号、长度和摘要，原位置映射保留私有。

首次批量写入log时，本地exec因单个argv过长而拒绝。第一份provider响应保留后改用分块写入，另外七份不可变终态日志通过只读GET再次取得；此收集故障和恢复过程保留，没有触发CI或目标重试。

SAFE文件通过字段白名单派生。下一步由另一工作组读取封存原件并独立验收；collector没有代签。此次CI和归档比对不改变默认能力、不启用候选计算内核或真实资金，不完成持续万笔容量、撮合清算全链路、多节点恢复或生产批准门槛。
