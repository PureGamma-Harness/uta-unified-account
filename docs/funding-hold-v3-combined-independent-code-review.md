# Funding V3 combined source：独立有限 CODE 审查

固定源码 `2b1b2a6d493c3258ce0446b45959f76318cb17d6`，本审查提交的
parent 必须为该 commit。结论为 **CODE_SOURCE_READY_NO_NEW_COMBINATION_BLOCKER_NOT_RUN_WITH_ADMIN_SCOPE_DEVIATION**。
当前明确源码、接口和组合范围内未发现新增阻断；root 可另行决定首次正常 CI。
本报告不给执行 GO，不把组件 CODE、旧 CI 或测试定义当作组合 PASS。
机器记录见 [review-2b1b2a6d.json](../evidence/reviews/funding-hold-v3-combined-independent/review-2b1b2a6d.json)。

## 当前来源与接口

运行库为67文件/1494225B：66 Python 加 HTML。三份行情控制模块
`durable_commands`、`durable_process`、`sharding` 与 public e409db54 逐 byte
相同；其余64文件与 public27e9442d相同。manifest 的全部 bytes/SHA/origin
检查完成；pure funding module 也与原 ed81 的 blob15c91c4c相同。未改变默认
cache 参数：reserve_cache_size=0、market_cache_size=0。没有启用新的 hold、
产品、模式、订单类型或金融权限；activation_permission=false。

V2 mapper/test 保持 f8 原件，V3 mapper/test 保持6f7原件，完整响应 driver
保持cd583原件。V3 mapper 仅六项 Constant 与V2不同；逆变后其余 AST 精确
相同。当前目标的13组 DTO 字段与 mapper 声明精确匹配，七个公开调用签名
能接受当前映射参数。运行控制只新增自己的 helper/参数，未形成 funding
pure 的运行接线。旧35c5/abaa/e0d6/6c777 CODE用于来源核对，本轮另审当前组合。

独立参考是 C7975266d/Fcab03a38 的11 exact blobs、168678B完整导出。两份V3
wire均33268B，SHA256 `6dd60f660a9a16c836b3572c7183d5a2085f2ff3ffae82fa66c7d4bdbf2b3bcd`。
参考/generator仅用stdlib；自检仅用这两个模块及新V3 manual/wire。mapper仅用
stdlib和uta.funding_hold_pure；driver直接导入固定V3三模块。普通unittest discovery
将tests目录加入导入路径，新增依赖均在同目录。未见旧e6/V2程序依赖、3→2翻译、
缺失lineage补全或将参考算法/结果放入target包装层。69/54af仍是本系统给定数据的
前向规则，不能证明外部内容真实性、批准、真正历史完整或持久原子提交。

## 自动合并兼容性

readiness文件精确等于e409版，只将原一次financial_ready诊断表达式改为一次
recovered snapshot，并给同一assertTrue添加既有有限消息。e409离线腐坏fixture
完整保留：正常writer必须拒绝坏halted/pending flags并保持原state，只有关闭的
测试authority通过raw SQL安装坏数据，随后独立read path必须fail closed。
没有新增观测、wait、谓词放宽、TTL/lease/quote或恢复重试变更。

partial publication真实oracle保持PENDING、attempts0、result/error null和financial
snapshot不变；完整publication与显式activation后才校验实际接受及幂等snapshot。
这些源码与e409完全相同，不是旧REJECT断言的悄悄删除。

expired guard、fixture和负例均与e409精确相同。原387B whole-AST reference
SHA为52fd579f…，module hash仍6158b76f…；本轮核实原件与两个public sources
相同。当前ordinary方法hash为086bfd15…；delta中的旧方法为860dbe35…。
guard必须先核准这两个exact hashes，仅在内存替换该一个节点，再与原6158整模块
比较。recovery、financial assertions、capture、cleanup仍在完整保护中。负例仍要求
对ordinary或recovery追加Pass时，实际guard拒绝。未运行guard或负例。

## 完整值与首次执行门槛

driver比较全部七字段响应与完整operation value的typed canonical bytes：False
不同于0，数组顺序和额外字段不能消失。每例同时要求reference/target符合独立
声明的OK/REJECT/UNSUPPORTED；valid例不能靠双方reject通过。未知逸出异常保留
cause并变成technical failure。两loader接收同一序列化数据，输入前后均比较。

stream定义为有序唯一1024 seeds、10 operations、512valid/512negative；只有全部
完成后才输出length-framed request/reference/target hashes。source-only计数新增
98个test方法：22行情、18V2、19V3、33reference、5driver、1AST负例，无方法删除。
2298只是基于旧2200的预期发现数，实际generated/compared/test runs全为0。

driver没有另写每op的独立JSON Schema validator；target输出contract与reference
定义仍各自负责其范围。固定generator提供D1V3前缀，driver核schema3与唯一ID。
逻辑transport上限不等于内核/RSS/CPU配额，一般codec等价尚未证明。

V4显式allowlist仍66，逐名称等于当前runtime Python集合。pyproject、MANIFEST、
CI、package verifiers与validation runner均保持base bytes；现有recursive规则覆盖
所有新增.py/.json/.md，sdist verifier仍要求全部tracked paths。wheel仍仅含uta及
HTML；验证模块不成为运行入口。实际包、新组件installed功能和binary qualification
保持OPEN，不能从旧25 module paths或旧8 tests推导此次直接验收。

## 历史、行政偏差与交付

PR62较早source的2194及8个成功job保留其RAW I/O限制；PR63首次16f64 push312
失败不因PR成功消失，cause仍UNDETERMINED；PR64成功没有观测failed-recovery
formatter文本。这些均不是本次组合CI。本轮未读取或改变旧raw，未重写旧BLOCKED。

本轮有明确行政偏差：一次`git grep HEAD -- tools tests ...`过宽，其可能完整输入
上界312 blobs/5064097B包含4个压缩fixture，3个报告binary matches。因此不签严格
explicit-source/no-archive流程合规或全会话物理I/O证明。没有解包、解析、安装或
执行归档，也没有为修复偏差重读归档。第一次行政AST helper在literal_eval误处理
CONSTRUCTORS时失败；此前runtime/verification/export/wire检查已完成。后续限定
literal字段的helper完成静态检查，独立ledger为35 reads/711209B。两次均未导入或
调用任何目标程序。偏差与helper错误完整保留在JSON，未洗为目标失败或重试。

独立worktree初始HEAD exact且clean；部分输入因共享sparse未物化，采用明确Git
blobs读取，不恢复source。没有main index、author目录、read-tree/reset/clean或
sparse reapply变更。没有target/reference/generator/validator调用、目标import、
bytecompile、test、SQL、actor/observer、proc/PID lookup/signal、network或CI。
H1/AuthDB8先前automatic-review拒绝仍NOT_RUN，没有重试或bypass。

只新增本文与JSON两份SAFE，提交不push。root可独立决定首次push/PR正常CI并保存
Python3.10–3.13实际full-field summary或first failure、source/package reports，再作
独立RAW审查。本报告不给执行GO。D2始终BLOCKED；真实ACK/outbox、全入口持久fence、
整期原子性、恢复、capacity/HA、10000/s、30分钟、实际24h、真实资金及production
均未批准。回滚仅revert两份审查资料，保留原件、失败与所有确认经济记录。
