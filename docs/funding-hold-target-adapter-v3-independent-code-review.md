# Funding target adapter V3：独立有限 CODE 审查

固定 `6f7a5a872b05a3787a347e164ae7075d1282aca9`，parent
`8e3db069b2aa0f19a1ac4fd62d32ae79afe6f267`。结论为
**CODE_CLOSED_FOR_EXPLICIT_V3_MARSHALLING_DELTA_NOT_RUN**。
本次对五个不可变候选文件的包装层静态复核未发现新增阻断；这只关闭显式
V3 marshalling delta 的 CODE 范围，不是目标金融行为、测试、差分或运行验收。
机器记录见 [review-6f7a5a87.json](../evidence/reviews/funding-hold-target-adapter-v3-independent/review-6f7a5a87.json)。

## 来源与物理固定

独立 worktree `/workspace/uta-funding-hold-target-v3-6f7-code` 基于候选创建，
branch `review/funding-hold-target-v3-6f7-code`。五个变更均为新增文件，已完整
读取实际 mapper475行、测试209行、文档、candidate JSON 和 wire1198行；
物理 bytes 与固定 Git blobs 全部相同。candidate JSON 中四项显式 pin 均匹配；
该 JSON 自身没有自引用 pin，本审查另记其完整 SHA，不把它算作缺失 pin。

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| docs/funding-hold-target-adapter-v3-code.md | 2147 | 4b01abb0f88fa33d8b239f42bdbbc2ce113949537a7f74fe1f4b859c652edf90 |
| evidence/designs/funding-hold-target-adapter-v3/code-candidate.json | 1677 | d0aa4a8d17c03fdd6d3ec75a4b4f7a974673f1774b798f76751f7774ebf287b1 |
| evidence/designs/funding-hold-target-adapter-v3/wire-contract.json | 33268 | 6dd60f660a9a16c836b3572c7183d5a2085f2ff3ffae82fa66c7d4bdbf2b3bcd |
| tests/funding_hold_target_adapter_v3.py | 24999 | 5953f9b5ccc1730f1ebb2d57707d73b339376a9a96159f244a1e256241eb6821 |
| tests/test_funding_hold_target_adapter_v3.py | 12022 | c42d2a813ff59963ffbeb3ca09f89cc42abc47c7302d02201411ab9006e9546f |

wire 与独立 `d3586666377d2d4bfcf61fbba0f0c51e08eca64d` 的 V3 wire 逐字节相同。
其 `$defs`、operations、bounds、resource_contract、hashes、natural_slot_order、
response_cases 和 native_rules 均与 `061580ce8c13120751bde4c4ce631b9dff25aa67`
旧 typed wire 相同；版本与显式69/54af lineage语义为新冻结项。061原件仍是
31492B/SHA d7d782e8007a0b4f9602483fb5ea2a373ac4bc42324f0fef94ba311bc7c2e3be。

## 六处变更与十九个定义

直接对照 `f8ece4c2257f2340e4b59fc0a113ac2b96ff9115` 的 V2 源，AST 仅有六个
Constant value 差异：module doc协议、wire SHA、wire路径、required envelope
version、版本错误标签、emitted envelope version。将这六项逆变后，源码 bytes
及不含位置属性的 AST 均与 f8 原件精确相等；其他函数体、声明和 guard 无变化。
f8原 V2 module/test 在候选内也逐字节保留。旧 `35c5b22b` 的有限 CODE 结论只
提供来源背景，本次仍逐项检查当前源，未将旧报告借作 V3 功能或数值证明。

测试类直接计数为19个 test_ 方法。移除新增
`test_previous_envelope_version_is_not_implicitly_translated:23`，逆变 module/class、
request helper 的 schema/case_id 与两处 encoder patch 字符串后，AST 精确等于
f8 原18个定义。新增定义要求 schema2 抛 WireReject；当前 `evaluate:415–416`
在 `_call` 之前确切要求 native int3，`return:444` 发 schema3，无3→2翻译。
嵌套 DutyKey.schema1 保留原义。19个方法全部 **NOT_RUN**，定义不是通过证据。

## 当前源中保留的 guard

`evaluate:440–443` 在 business catch 之外验证实际 DTO 返回类型、编码并验证
完整 selected operation value；`_encode:120–141` 保留确切 native 类型、DTO
全字段和固定 flag 检查。natural_slot 先要求六字符串 tuple；policy payload
保留实际 policy DTO；wait_records 序列化实际 validator tuple 的全部 IDs/order，
不重算、排序、去重或以 count 替代。这些是源路径事实，无实际 full-field PASS。

`_checked_intermediate:301–311` 在 decompose 下游调用前检查真实 Totals 类型及
完整 encoded wire；坏中间返回技术失败。两个输入已接受后的下游 HoldError
仍转为保留 cause 的 AdapterContractError。成功路径 encoder/schema/坏return
错误不进入业务 REJECT；只有确切已知 InputReject/HoldError/HoldUnsupported
归类，未知 subclasses、target/constructor异常保留技术失败。

`_validate_output:296–298` 先完整 meta 后 matcher。meta 无 value 参数，完整走
每个 oneOf 分支、object property、array item，并保留 exact keyword native
类型、local ref存在性、active-path cycle、depth32/work8192检查；matcher 只把
_OutputMismatch 当 alternatives 的 value mismatch。固定十个 selected output
closure 的独立 JSON 图计数最大99 nodes/depth9；此统计未调用被审 validator。
它不覆盖 request.input 的开放 transport root、未选 root 或一般 JSON Schema。

`_dto:94–117` 只逐字段构造给定 Stage/history，nullable refs 原值传递，不填补
missing exposure/cap/history，也不从历史恢复 refs。金额与状态运算仍委托 target；
包装器没有新增金融方程、reference算法或答案。69a3e32e/54af0876 是独立的
本系统前向规则：direct final 两项 lineage null；viaU final 全字段保留历史 E/C。
当前 bridge 的 typed shape 无法认证内容、批准、完整外部历史或持久原子提交；
本审查没有读取 target算法来判断这些业务规则是否已实现。

`_wire_contract:148–155` 保留 hash固定、65536B文件上限；native tree 与decoder
保留2MiB raw/compactASCII、depth32、250000 occurrences、128位十进制数字
等既有检查。它们是 validation caps，不是RSS/CPU硬配额或完整codec等价证明。
本次不覆盖 EOF/IO framing 或未来外部 differential caller。meta-before-match
假设一次检查/匹配间固定 native JSON schema graph 不被并发篡改，不签任意
恶意可变schema、regex全部语义/性能或一般2020-12支持。

## 隔离、未运行与门槛

只用 Git tree/blob身份检查运行库：候选、parent、public PR64 d128ee6e 与
`ed81c424e3be7c004331bcd8340421d60063fcb6` 的 uta tree 均为
`344a63fa30e18079b335ad69bd326f92324f279c`，67files/1479474B；puremodule
`uta/funding_hold_pure.py` 只核 Git blob `15c91c4c9ca109db906bc7c8a434751afbe78159`
及23348B，不读其算法。运行库字节未改变，不代表其金融功能已被本审验收。

本轮无 adapter/reference/validator import、call、bytecompile、测试、casegen、
SQL、proc/PID lookup或signal、actors/services、network或CI。AST只作数据parse/dump。
未读 reference financial core/casegenerator/answers。旧 H1/AuthDB 拒绝保持 NOT_RUN，
没有重试或绕过，未重写旧 raw/历史结论。所有19测试、金融语义、codec等价、
full-field差分、实际资源和normal CI仍 NOT_RUN。执行组合、caller、完整sources/
inputs及首次资源scope须另审；本报告不给执行GO。D2无条件 **BLOCKED**，
activation_permission=false，capacity和real-funds production仍未验收/NO_GO。

只新增本报告和JSON两件SAFE资料，未改候选五件、历史源码、作者工作区或主index。
新worktree继承共享sparse配置，五件新路径初始为S且物理缺失；仅在独立worktree
用精确Git blobs物化，未read-tree或sparse reapply。作者HEAD6f7/clean作只读核对。
交付commit不push；回滚仅revert本审查，保留旧源码、计划、raw及确认经济记录。
