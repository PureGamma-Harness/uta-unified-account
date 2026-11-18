# PR38 首次 push / PR CI：两轮均 FAIL，原件封存

首 head 为 `9b4fcf5df3615c8bcddc8dc37cb35f9a24d21439`，tree `91cfb3c27447b26357322a211345df61a57b6be2`，base PR35 `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`。PR38 是 Draft。PR merge commit `81b1d4f08c96ca3b3ad83108af07f4199eba1c86` 的 parents 为 base/head，tree 与 head 相同。push/PR 两轮均为 attempt1；collector 未重跑、修复、build、执行产品或再次push。

| event / run | Python3.10 | 3.11 | 3.12 | 3.13 | whole |
| --- | --- | --- | --- | --- | --- |
| push `44231349622` | success | success | unit ERROR×2 | success | failure |
| PR `44231370634` | unit FAIL×2 | success | success | success | failure |

失败 job 分别是 `134556896833` / Python3.12 与 `134556964156` / Python3.10，均在 step5 `Run unit tests`。后续 package/installed 等步骤按 provider 原始 jobs metadata 保留 skipped，不能算通过。其余六个 job 成功。两个失败 unit artifact 均实际记录2102条、worker exit1、skip0、source unchanged；未下载六个成功 job 的 unit artifact，不额外声称它们的逐条计数。

push 的两个独立 ERROR 是 owned_startup 的 credit projection corruption 测试与 startup_write_contention 的 unrelated authority 测试；都观察到 `WriterFenceError: writer lease expired; renew cannot revive it`，栈到 service.py189 → startup.py312 → writer_fence.py533/295。PR 的 healthy real workers 测试观察到 readiness `market_stale`；另一个 incomplete-watermarks 测试在开头 activate() → publish_market 的 publishing assertFalse 处得到True，尚未到后续offline mutation。每条case的独立安全栈、源码SHA及相对base零diff记录在 `failure-classification.json`。共享消息/栈不是同一根因证明，不归因为flake或DB corruption，也不对M05作推断。

两份失败 unit.txt 均逐条出现 D2/export/D1 三模块的76个唯一ID且为ok（53新增D2 +23既有D1）。这是本次2102条失败运行内的局部观察。原3040首120与8594首76是不同source、相互重叠的历史scope，仍按原件单独保留；不能合并成196通关，也不能用局部ok覆盖whole failure。

额外仅取一份成功 job 的小 package-validation ZIP：PR Python3.13 job `134556963919`，artifact `14395731238`，59103B，SHA256 `f0f261c5b77d483281195352e34b74f5934b96f1e595b634d44c1a2881f79a1b`。首19members CRC全过；两个原始JSON报告的source为PR merge SHA，7checks全true、installed8/8且isolated，production_approved=false。report列明全部38个D2交付路径及两条旧literal inputs已被sdist选择，missing/mismatched均空。这是精确source的provider verifier report，不是本地重建或独立检查原始wheel/sdist；二者均未下载，也未下载约50MB的 `uta-wheel-*` provider artifact容器。报告中的wheel为359577B、sdist为50748499B，约50MB不指wheel文件本身。单job正向结果不改变两轮whole failure。

失败unit ZIP各仅取一次：push101078B/SHA `df928133099dd661620a88206136b67fe31e3fc646ef2c8cb54e5535e0206010`；PR90632B/SHA `f6db01c0b775453ca7beeba0a7cdfb8cb4dcd48ad8c75350a8b9d8835863d95f`。digest/长度与provider匹配，各3members首CRC全过，unit.txt SHA与summary一致，source-before/after maps相等，76闭包四文件SHA逐一等发布head。首原job logs、ZIP、摘要及metadata均不裁剪或重写。

安全OWN在 `evidence/runs/pr38-first-ci/`：59份原件/投影共1364766B，加seal与本说明；后续独立closure单列。provider JSON按connector返回的UTF-8内容保存；job log为connector解码文本，receipt明确没有HTTP wire headers。查询实际时间与间隔均在observations-index保留，artifact处理产生的较长间隔不改写。签名下载引用只留私有0700/0600目录，OWN仅含其bytes/SHA；小package ZIP留私有，仅两个安全JSON与CRC manifest导出。固定PEM/credential/signedURL模式计数为0，这不是安全审计。独立只读review已闭合（EVIDENCE_PASS），见independent-review-closure.json；首seal/final-status里的PENDING是历史原件，保留不回写。

controller仍为 `D2_COMPANION_EXPORT_ENABLED=False` / SHA67a97e55…，runtime UTA tree仍等6010。发布前的20flags是原冻结快照，本collector不回写；ordinary CI的实际执行另在final-status记录，不产生actualM06授权。kernel backend仍NOT_IMPLEMENTED/NOT_VERIFIED，M05仍UNKNOWN/P_NOT_RUN/05spent；production、10k/s、HA、真实资金与actualM06全部false。新safeOWN不push，由root用skip-ci方式另行整合。
