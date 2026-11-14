# 真实双侧清算的短时开放环探针

工具：`benchmarks/run_matched_liquidation.py`。它只使用公开的 `ExchangeService`、风险监督器和 `Matcher`，不调用手工成交入口，不以风险计算次数、撤单次数或双方分录条数充当清算成交。账户、价格、资金和对手深度都是合成数据；规则使用显式 `synthetic_policy()` 版本化 Cross 配置，PM 未启用。

这是一份 **最多30秒到达、最多30秒软排空的诊断工具**，没有完成持续30分钟万笔验收。运行中没有把旧行情不断改成“新时间”以掩盖断流；90秒行情时效是明确的短探针配置，长稳需要另行实现、计入成本并验收的真实行情扇出路径。`--duration 1800` 会明确拒绝，而不是偷偷缩小测试。

## 金融链路与成交计数

每个 case 建立两个实际账户：受险账户 USD 1000，对手账户 USD 100000；通过真实的90单位买卖限价单、价格100形成持仓。一个分片内所有case共用 `BTC-PERP`，不以每case创建新交易对来消除热点。各分片是独立本地撮合簿，工具不宣称跨分片撮合、全局价格时间优先或HA。

预置完成后对每片发布一次mark90的真实风险快照，受险账户权益96.4、MM405。风险监督创建持久只减仓单；任务只提供两张45单位真实对手买单，逐次调用撮合。对手买单也只减其原有空仓，无新资金或隐含借款。成交按实际FIFO归属，某线程处理的case不一定就是该线程撮合到的受险账户，工具按回执 `sell_account_id` 统计实际对象。

每个唯一持久match receipt代表 **一笔** 清算成交；其两侧fill/仓位/资金分录必须已经一起提交。一次45单位成交有两条结算腿，但只计一笔，不把45拆成微量成交来提高指标。初始90单位开仓也有真实回执，但被明确排除在清算计数之外。

完整case的独立现金流为 `1000−开仓费3.6−平仓损失900−两次平仓费3.24=93.16 USD`。最终仓位应为零。`liquidity=none` 不提供对手单，不会生成任何清算成交；`half` 每case只提供一张45单，报告实际成交量及剩余风险，不承诺同簿FIFO下每个账户都恰好处理一半。

## 开放环、时间和故障结果

主线程按绝对 `monotonic_ns` 时刻投递任务，不等待前一任务处理完成；任务队列满则记录该唯一case为overload。工作线程独立处理，输出队列有由有限case数量推导的显式上界。参数 `cases<=512` 限制这是有界的短探针，而不是声称支持无限流。

风险触发是所有预置账户的统一行情冲击，不是任务泵每发一条才出现一个新风险。因此报告同时区分：

- `scheduled_case_to_complete`：计划任务到达至处理完成，包含排队。
- `shock_to_first_confirmed_trade`：真实行情触发至各实际受险账户首笔确认。
- `shock_to_each_confirmed_trade`：真实行情触发至每笔实际确认。
- `shock_to_recovered`：真实行情触发至监督器确认恢复。

所有分位数都从保留的精确纳秒样本计算；P50/P95/P99/P99.9使用nearest-rank，不抽样。统一shock后等待工作线程初始化和任务泵的时间计入shock延迟，没有从触发延迟中隐藏。

预置时间、shock后worker初始化、到达窗口、执行/排空、重开对账分别报告。吞吐分母包含到达窗口和实际排空时间中的较大值。软排空期限不会强杀已开始的金融事务；在途事务继续join，超出时间仍留在吞吐分母，未执行case记unknown并保留实际风险。软完成期限不是回滚指令；迟到的已提交成交单独计数，不视为及时完成。

业务拒绝、技术失败、未知、队列过载和期限超出均保留。若回执在存储中已提交、但调用者没有观测到，恢复时标为 `recovered_unknown_trade`，没有可靠完成时刻，不计入已观测确认吞吐。执行后重开每个库执行完整 `reconcile_exchange(matching_only=True)`，并检查实际平掉量加残余量精确等于初始90×case数；不能超量、反向或把未成交量当作已处置。

## 运行与证据

```sh
python benchmarks/run_matched_liquidation.py --cases 20 --duration 1 \
  --workers 2 --shards 1 --queue-capacity 64 --drain-seconds 20 \
  --output /tmp/matched-liquidation-new --smoke
python benchmarks/run_matched_liquidation.py --cases 2 --duration .1 \
  --liquidity none --output /tmp/matched-no-depth --smoke
```

目录必须是新路径。每次保存：`environment.json`（代码commit、全部运行模块和工具SHA-256、Python/SQLite/CPU配额、规则版本）；`arrivals.jsonl`（每case、风险计划、逐笔完整回执、恢复和未知）；`summary.json`；`manifest.json`。SQLite文件只保留在本地受控目录，不加入公开结果包；记录的reconciliation结果来自实际重开后的库。

默认容量门槛保持 `>=10000 unique committed liquidation fills/s`、`>=1800s`、足够实际对手量、无未完成账户及技术失败/过载/未知/超期。短探针的duration门槛必然失败。`--smoke`只使工具自检成功时退出0，报告的gates和`production_approved:false`不会改变；不加smoke时未达容量退出2。技术失败退出1。

该工具尚未验证订单/查询/行情的混合长稳、真实市场盘口深度、外部交易所、跨区复制、风险委员会校准或真实资金审批，不能用此探针结果关闭P1生产门槛。
