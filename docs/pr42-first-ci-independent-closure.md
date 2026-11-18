# PR42 首 CI 独立复核：完整性通过，八个 job 仍失败

结论：**FIRST RAW EVIDENCE BINDING PASS；CI 与资格门槛仍拒绝。** 审查固定 author seal `0cd6192f262f868a59c1f18cc7ffd17964917eaf`，源 C `f510bf5fea852ca04c87930077861c312320141f`。相对 C 仅66个新增 docs/evidence 路径、5929896字节，没有运行时代码或旧记录改动。首 seal/PENDING、CI43 和后续7030修复保持独立。

八个原 ZIP 共786919字节，均与定向私有原件、公开 Git、副本及 provider 长度/SHA字段相符。24个成员的 CRC32、长度、SHA256 和两侧逐字节副本一致；每份只有 summary.json、worker-result.json、unittest.txt。八份368项 source before/after maps 均相等，逐文件匹配精确 C 的 Git bytes。PR 的实际 source commit 仍为 fea8353 merge；其 base/head parents 和 tree 与 API 留存投影及 C 的 Git tree 对应，不伪造本地 merge checkout。

两轮 attempt1 各四个 job 全部 failure。每份实际2102tests、25ERROR、0skip、exit1；push3.13另有1FAIL。独立解析完整 footer 得到201项：200项 CreditArtifactError 和一项 SH capture-undo FAIL。成功 case 输出中的预期 child traceback 未计为 footer 失败。25个唯一 ERROR ID 在八份原件中一致，但逐 job 原标题、消息及原 footer body SHA均单独核对。

961条 frame 的路径、精确行、函数显示名、原显示行、Git blob/SHA256逐项对应；有关文件与 PR38 base17e 字节相同。原 ERROR 最终消息均是 unsupported loaded financial constant type，具体 unsupported attribute 仍 NOT_OBSERVED，cause仍 UNDETERMINED。credit_artifact_unavailable 是 raise 分支的源代码 literal，不是从异常对象采集的 runtime code。共同异常类、共同 raise、source Enum 静态猜测及源文件相同均不能回填当时的具体 attribute 或共同根因。push3.13的唯一 FAIL 保留为原1456行 capture undo horizon 失败，不改判为别的恢复阶段或上述 ERROR 同因。

worker与summary的九字段形状按原生类型核对：lease_observations 为 list[]，truncated 为 bool False，其他字段逐类型和值一致。这只证明报告语法。原 passed/unittest_passed 为False、errors25、worker_exit1，raw末尾是FAILED；原消费者还要求 passed/unittest_passed True、错误/退出为0与完整OK结尾，因此这些输入必须拒绝。此为静态合同判断，没有执行 qualification 函数，也不把先前 limited pure 结果转成整体通过。

八份完整私有 decoded job logs 共214686字节，只读用于长度/SHA及红删谓词比较。独立按六类 pattern 的 OR 重建公开 SAFE：命中的私有行被替换为固定占位行，其余行原字节保留。八个 receipt 的原/SAFE长度、SHA、原行号和完整原件仅取一次标记均对应。公开 SAFE 从未当作完整原日志；实际 headers、原 connector、签名引用和值未被此次复核公开。

两个表示域需明确保留。SAFE是行内容替换投影，不是无标记的原日志；final_message 是trim后的显示字符串，而原 final_message_utf8_sha256 覆盖带 leading blank 的原异常 suffix。独立 hash 验证按原 suffix 域完成，本文不改首字段，也不让读者误以为它等于trim显示串的SHA。

第二个独立只读 reader检查66个公开路径、八个ZIP和24个成员、八份SAFE日志：未发现实际 nonce/secret/signature/credential 值、真实 header 值语法、DB magic或额外二进制。authorization宽检索命中均为测试ID。此为定向检查，不是任意秘密不存在或全量安全审计的证明。

首次格式检查的父级 exit1、3330字节原stdout、原stderr空和未知的原git子进程exit均保留；没有回填为推测值。五份SAFE日志的30处原非敏感尾空格与封存路径/行号一致，后续狭义格式检查的空输出和exit0对应；没有trim原件。现有 MANIFEST.in 静态覆盖全部66个新增路径，包括八个ZIP；没有执行 build 或因此声称 package/installed 验证成功。unit失败后 package步骤仍为skipped，always-upload不构成成功报告。

本组只做定向 Git/text/ZIP CRC/JSON/hash/字节核对，使用 NOFOLLOW/NOATIME 与稳定元数据读原件。没有 API/网络/下载、target import/test、SQL、proc/PID、探针或重跑。证据完整性通过保持本轮全红；没有 phase2、生产、真实资金、HA、10k/s或完整金融平台验收。
