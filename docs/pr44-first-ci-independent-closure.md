# PR44 首 CI 独立 RAW 复核

结论：**选定 unit 与报告的首证据绑定通过。** 固定 SAFE `2055b347ac84c2232a868851952f2e49a4e9fde7`，source C `c2aa3cc4d2db7785a19d5f54352c0f893774582a`，base `e101598d83947aabd9c4c47ae47bbd0adeb9ec39`。原manifest12494字节/SHA256 `8899da214e69f1c68d452958ce0bf6ae281bdb6e563422c148bd9f5c7c2cace7` 与22个列出文件逐项匹配。相对 C 仅23个新增 docs/evidence 路径，源代码和旧记录未变。

唯一下载的 exact-push Python3.13 unit artifact14408608768 为101001字节，SHA256 `de0003fbe893e030de543da857de5c65f0e66c0ff795d0100144c666954407ad`。私有原件、Git公开ZIP、三个成员和各独立副本逐字相同；3个CRC、长度、SHA与provider字段对应。实际Python3.13.18/GCC15.2.0、SQLite3.46.1，2108tests/0FAIL/0ERROR/0skip、worker exit0，passed/unittest_passed true。六个新方法由冻结AST独立枚举并各单次ok；旧25个ERROR ID集合与不可变CI42首记录交叉一致，当前原文各单次ok，旧SH ID也单次ok。

W9/S9的九字段逐类型和值相等，lease_observations 为原生list[]、truncated为字面bool False。371项source before/after maps相等并逐GitC核对；保留计划的65项输入也逐CI/Git相等，其中61项为UTA Python源。HTML是package单独绑定项，没有计入这61项Python capture。保留输入只说明源字节identity，不转移原计划的运行时、执行或authority资格。

小package artifact14409875235 为60686字节，SHA256 `45ff29857d3fdd32b7b8e19259150bb80f20f948b3a1cd1dae22a32058b15954`。19个成员的CRC、长度、SHA和私有提取副本对应。七项archive checks true，installed8tests/0F0E0skip和八个命令return0，isolated true且PYTHONPATH null；helper原测试/Git/manifest/copy指纹一致。62个Python/HTML runtime hashes和重算aggregate匹配GitC及两报告；7144 required集合等于完整GitC，新32路径亦与真实base→C diff相同且全部列入。

公开决策同时核对七类primary及UUID/独立32hex。unit容器与三个成员均clear，原字节可保持公开。package的demo stdout、scenario stdout各有一个32hex候选；本复核只记录成员名与计数，不输出或复制候选值。完整原package ZIP和这些stdout保持私有，公开只包含三个独立clear的原报告成员及明确的metadata/selection投影与收据，没有伪造或另造“完整SAFE package”。没有大wheel/sdist下载或独立二进制封验。

push44263248587和PR44263298099两轮attempt1，各四个Python3.10/3.11/3.12/3.13 job whole success；unit与installed步骤成功来自已保存provider metadata。只一份unit原件直接核对，其余七份没有逐份计数/W9S9结论。merge e1b223的parents为base/C、tree与C相同；PR成功job的checkout行或summary未取，API绑定的限制保留，没有冒称从PR原文观察checkout。

新的完整managed qualification结果继续为null，本collector/reviewer未发起完整资格调用。普通CI、单份W9/S9形状和组件原文分别记录。f510旧首记录的specific attribute仍NOT_OBSERVED、cause仍UNDETERMINED；新源码Enum及当前逐ID通过不回填旧运行状态，也不把旧200ERROR或SH失败改写为通过。

三个collector准备事件仍单列为准备事件；未知的首次inner writer stderr继续UNKNOWN。当前unit/package archive parser首执行各exit0，原ZIP和CI没有重下、重写或重跑。已有MANIFEST仅静态覆盖这些新增材料，本复核没有build/安装。私有读取限定新scope并采用NOFOLLOW/NOATIME与稳定元数据，未读或导出transfers中的真实headers/签名引用。

本组只做Git/text/AST、ZIP CRC、JSON/hash及定向privacy字节核对；没有child、API、target import/test、SQL、proc/PID、探针或重跑。此次结论不批准Phase2、生产、真实资金、HA、吞吐或旧code-bound authority热换。CI42/43、首原件/PENDING与其他历史结果保留原source及scope。
