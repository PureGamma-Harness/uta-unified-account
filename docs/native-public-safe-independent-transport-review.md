# Native 公开候选：独立传输与隐私审查

审查固定候选 `b661241591dd11552e4347043156d0fe40c27f5f`，结论为 **PASS：仅限精确公开源码/证据传输与本次隐私边界**。没有目标功能、native、当前运行时、容量、生产或新执行授权。机器记录见 [review-b6612415.json](../evidence/reviews/native-public-safe-transport/review-b6612415.json)。

本轮不重新审查原 SAFE 的金融或原始运行正确性。审查者曾编写来源 `75fe3a16` 的7个 SAFE 文件；本轮仅验证另一位交付作者的复制字节，其原始正确性仍引用另一组 `8b7e30bb` 的 RAW 审查。guards6 原始正确性同样保留 `8e78ac2b` 的独立审查，不能把本轮传输复核当作原件自签。

## 精确传输与来源

候选只有一个 parent：公开基线 `c3e937a967711cd5cae7293ac3bf63c8260d8528`。已检查根负责人指定的三条私有历史排除项，均未进入 ancestry；origin commit 的只读证据引用不等于把其历史合并进公开分支。

新增48个文件严格等于44个指定导出与4个新元数据/说明文件。44个导出合计 **296,169 bytes**，每项 origin/candidate 的 Git mode、blob、字节数和 SHA-256 均一致，候选物理文件也逐字节一致。Git mode 均为100644；实际导出文件均为0600、普通文件且无执行位。0600是工作区权限，不影响 Git 的非可执行文件模式；本轮没有调整任何作者文件权限或字节。原61个 UTA 运行时文件的 Git tree 与公开基线相同。

4个新增文件的范围精确闭合：候选说明、export manifest、作者 privacy review 和 source closure。其 Git/物理字节一致，JSON 无重复 key 或非标准数值，逐项声明与传输数据核同。没有额外原始数据库、归档、control副本、秘密材料或运行结果文件混入本次新增集合。

## 70项与15项分别成立的范围

| 清单 | 独立核验 | 限制 |
| --- | --- | --- |
| 当前 controller70 | SHA-256 `e3c62d9ee7f2aac50eb1335835c60d45ca5fdd5eef71fb0d5a62150f10559c4e`；70项 candidate Git 与固定 be373 源字节相同，分为64项公开base及6项精确导出 | 属于 Git/source-byte 闭合，不是运行前全量 physical preflight |
| guards15 | binding SHA-256 `c38550ace6e248c6229698a2fb16cf611fddfe19864ea30e58486015c7463beb`；15项 candidate物理/Git与固定76827a4a一致 | 不证明运行、当前环境或任意native安全 |
| 旧 native70 | 67项匹配，pilot/native-host/owned-workers三项仍为早期版本 | 原字节保留，显著标为 HISTORICAL / DATA_ONLY / DO_NOT_EXECUTE |
| 13项标准库引用 | 原 resource map 的13项历史记录及意图路径保留 | 不读取当前标准库或二进制作认证，不自认证runtime capsule |

候选工作区为 sparse：当前70清单实际存在9个物理文件，其中6个为导出、3个为公开base benchmark，其余61个未物化。本轮未补 checkout、未移动源文件，也没有把 Git 闭合说成全量物理运行前核验。以后若要执行，必须在新独立计划中重新完成全 physical70 与 runtime/source/namespace 认证。

## 有限隐私决定

经单独授权，只读取37份固定已封存 JSON 作泄漏负检：native30份、guards7份。提取的10个强实际身份参考值包括数值进程/会话/出生计数及不透明身份值；在全部48个候选文件中均无命中。未输出或保存这些值，也未探测任何活跃进程。额外完整私钥/证书块、签名URL及原始数据库/ZIP容器检查未见命中。这是有限负检，不是对所有潜在秘密或漏洞的完备证明。

根负责人对 guards 既有 SAFE 的 `capture_observation` **仅以下四字段**明确作出发布政策批准，允许原字节保留：`host_start_ns`、`host_before_receipt_end_ns`、`monotonic_start_ns`、`monotonic_end_ns`。它们是已经由原 RAW 审查接受的执行收据时钟/provenance；本轮不把其值再次复制到审查记录。此批准不扩展到其他绝对时钟、birth start_ticks、boot ID、lease/epoch代际、进程身份或秘密，也不是自动认定所有 metadata 安全。

已批准的通用工作区路径、历史 CODE argv、固定禁止身份集合和显式合成 fixture 值原样保留。它们不是实际运行身份、新可执行命令或旧目录复用许可。实际身份、私钥/capsule/TLS、实际生成绑定、签名URL、原始control及数据库/归档的发布仍不获授权。

## 执行与证据边界

本轮只做静态 Git/文件/JSON比对及11个Python文件的 AST 语法解析；没有目标 import、字节码编译、测试、SQL、进程探测、native、CI或网络行为。源码中存在可控制进程和存储的API，不因传输通过就变成已验证沙箱或运行授权。

历史 guards6 实际保留的是6个选定mock方法（原3项与新增3项）；计划中的7项 required results不是7次测试运行。原 native 只有失败样本中两个worker的有限清理记录。本轮不重签这些运行结果，不推断任意native、C扩展、HA或恢复完备性。

原计划的 false/0 仅表示原 CODE 时点；本候选已保留后来的首次 native **FIRST_FAIL**：34 offered、25接纳回执、8业务拒绝、1控制拒绝，未完成重开逐笔对账。不得用旧 false/0 抹去首次失败，也不得把25回执称为对账成功或成交容量。本轮没有重试或修改44个导出文件。

审查过程中纠正过两项自设行政假设：工作区权限应记录为0600，而非强求0644；sparse公开base应按Git字节闭合，而非自行物化。四个收据时钟则由根负责人逐字段明确批准。它们不是目标运行失败或目标复跑。

当前没有需作者更改导出字节的传输/隐私阻断。后续只有新的源清单、runtime、namespace、不可变计划、资源预算和单独执行批准才能开展试跑；功能修复、撮合/账务、重开对账和用户容量门槛仍分别验收。回滚本审查仅移除这两份新增审查文件，不改候选44个导出、4个作者元数据、原始SAFE/RAW或封存原件。
