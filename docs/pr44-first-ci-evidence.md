# PR44 首 CI：push 与 PR 两套 attempt1 均 whole green

发布 head C 为 c2aa3cc4d2db7785a19d5f54352c0f893774582a，base 为
e101598d83947aabd9c4c47ae47bbd0adeb9ec39。PR44 初次观察为 Draft。
API 实际 merge 为 e1b223aacb89bf6cafe64d101ddcb5efc444481f，parents 精确
为 base/head；head 与 merge tree 均为3694eb02a907c02ec721f4cfc106ee454069eee9。
这两项 CI qualification 分别保留，没有把一个组件 PASS 推成整体 PASS。

| 事件 / attempt1 | run | Python family | job | provider whole result |
|---|---|---|---|---|
|push|44263248587|3.10|134661485424|success|
|push|44263248587|3.11|134661485337|success|
|push|44263248587|3.12|134661485340|success|
|push|44263248587|3.13|134661484927|success|
|PR44|44263298099|3.10|134661635837|success|
|PR44|44263298099|3.11|134661635349|success|
|PR44|44263298099|3.12|134661635909|success|
|PR44|44263298099|3.13|134661635994|success|

八个 job 的 unit、后续检查、package/installed 步骤均完成成功，两 run 最终
completed/success。观察 poll-002 在08:09:13Z完成后停止轮询，没有 CI rerun、
dispatch 或 push。初次 run-list、初次 jobs 与后续 attempt-specific 响应分别保留；
同一资源的重复观察间隔至少60秒，不把稍后写文件时间伪作观察时间。

只获取了额外授权的一份成功 exact-push unit ZIP：
artifact14408608768，101001B，SHA256
de0003fbe893e030de543da857de5c65f0e66c0ff795d0100144c666954407ad。
它与 provider digest/长度相同，三个成员首读 CRC 成功，原 unittest hash 与
summary 的 test_log_sha256 对应。实际 code_commit 为 C，运行时为
Python3.13.18/GCC15.2.0、SQLite3.46.1；2108 tests、0 FAIL、0 ERROR、0 skipped，
worker exit0，passed/unittest_passed均 true。未借用本地3.12.14结果或 binary。
新 LeaseObservationTagArtifactTests 六个方法在该原文中各单次ok。
其余七个成功 unit ZIP 未取，不能据此声称逐份计数、逐方法或 schema 已核。

这份实际 worker 恰9keys：原7字段及 lease_observations、
lease_observations_truncated。worker 与 summary 的这对保留字段均为原生
list[]及原生 bool字面False；九项类型和值完全一致。summary 的371项
source before/after maps 相同并逐项匹配精确 C Git bytes，原 tracked-clean
与 source_unchanged flags 均 true。retained834计划的65 inputs、其中61个
UTA Python源，也与该 CI capture/Git逐项一致。HTML另为package的Git绑定项，
没有伪称包含在这61个 Python capture 内。

旧 PR42 八份各25 ERROR的相同25个唯一测试ID，在所选新unit中各单次ok；
旧 SH FAIL ID也单次ok。这里分别记录当前0 ERROR、这些ID的当前结果及整个
provider矩阵成功。f510原件中的具体 unsupported attribute仍NOT_OBSERVED，
具体cause仍UNDETERMINED；没有用当前Enum源码倒填当时运行状态，也未把旧
8×25ERROR或原SH FAIL洗成PASS。旧原件、旧PENDING、834首pure6及其独立
CODE/RAW结论保持原source和scope。

一份成功 exact-push smallpackage报告为artifact14409875235，60686B，
SHA256 45ff29857d3fdd32b7b8e19259150bb80f20f948b3a1cd1dae22a32058b15954，
19成员CRC均通过。报告的7checks全true，7144 required路径集合与 C Git完全
一致，新32路径均列入，无missing/mismatched。62个Python/HTML runtime
hash与 C绑定，runtime-tree digest为
aff7dc857e67dbcf0ee4f81db5562a5df01f36f1758e496a40d1da109bbd4b75。
installed报告为8tests/0F0E0skip，8命令return0，Python3.13.18/SQLite3.46.1。
这里只取得报告，不下载大wheel/sdist，不冒充对那些二进制的独立封验。

所有原 ZIP先留新0700私有目录，以O_EXCL0600文件和provider SHA保存。
unit ZIP的container/成员凭据、private-key、签名URL、nonce/context、DB magic
及额外UUID/独立32hex定向检查均clear，因此公开原ZIP和三个成员，保持原字节。
package的额外32hex检查在demo stdout和scenario stdout各命中一个候选控制值。
整个原package ZIP及这些stdout继续private；公开仅独立clear的原报告成员和
带receipt的metadata/selection投影，不冒充完整原package archive。
不公开实际匹配值、headers、connector签名下载引用、DB或key。
没有失败 job，所以没有获取任何 full joblog；若有，政策仍是原全文private，
public仅明确标注且有receipt的SAFE删减版。当前没有公开joblog全文或伪造SAFE log。

collector的三个准备错误单列保留：私有base64 writer最初包含here-doc换行而
wrapper返回save-private错误（当时内层stderr未留，保持UNKNOWN）、外层JS构造
trusted parser源码时的SyntaxError，以及把unit61项Python源误当package62项
Python/HTML源的输入检查。它们均在对应archive处理/文件写入前发生，修正只在
新的collector代码与数据准备；原ZIP、CI source及结果没有重写，也没有目标
测试/CI重试。原私有writer源码/v2和实际捕获协议留存私有；完整archive parser
与report分析的首次执行均成功。不能把collector准备故障说成CI失败或隐去它们。

实际私有/公开payload仅一unit ZIP和一smallpackage，共161687B，远小于各自
2MiB/1MiB与整体64MiB限额。没有额外成功unit、PR成功package、大installable
下载，亦无本地target import/test/build/install、SQL/connect、PID/probe/signal
或native动作。GitHub API读、Git/file读与有界标准库ZIP/JSON检查之外无新动作。
公开metadata的每次导出均经receipt，全部路径按现有MANIFEST规则静态覆盖，
未build或因此声称新的打包运行。

API merge的parents/tree已独立绑定；由于未取得成功PR的unit/log，本collector
不声称从其原文逐job观察了checkout行。所选push summary直接记录 C。
whole-PR成功来自实际provider状态及同tree绑定，不伪造本地merge checkout。
W9/S9形状、组件测试和whole CI是不同证据；本组没有发起或取得新的完整
managed qualification结果。Phase2、生产、真实资金、HA、吞吐及热换旧
code-bound authority均不因此批准。

SAFE证据位于evidence/reviews/pr44-first-ci/。old历史、当前原件、redaction/
export receipt、source binding、独立head/merge终态、组件结果和report-only
package结论分文件保存，供另一组只读审查后由root单独整合。
