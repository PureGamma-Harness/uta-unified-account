# 持久资金费义务：账户与账务独立 CODE 审查

精确源码 `901700637b3bb329cbb5729227e5b654dd8a00b6`、tree
`60ad7104beabed0cd00eb08ebe4924bad31b2248`，以公开PR48的6ba5为基线，规格为69f6。
账户与账务审查结论为 **NOT_CLOSED：两个可恢复数据错误路径被写为终态 REVIEW**。
本阶段仍NOT_RUN0，不是目标测试失败；未导入、编译或执行目标/SQL/测试/线程/进程/PID/
CI，也未触碰已封32原件或首次CI。

FUND-OBL-001：capture取到fresh USD-only行情后直接索引目标mark。MarketSnapshot明确
允许空instruments，原service验证会跳过缺失symbol，因此有效费率/准时窗口下可到达
KeyError，随后被归为REVIEW_REQUIRED。规格承诺缺mark仍WAITING_DATA；当前恢复行情后
也无法再claim，故是本切片功能阻断。应明确识别缺少必要边界报价，而不是把所有KeyError/
ValueError统称可重试。

FUND-OBL-002：已有有效cut后，当前fresh行情缺BTC mark时，原_risk把
missing_instrument_price包为ServiceError/risk_unavailable。apply的SAVEPOINT会正确回滚
现金与风险修改，但WAITING_DATA分类没有该数据路径，转为终态REVIEW_REQUIRED。应结构化
识别临时行情不可用，保留非法库存/规则/账务错误的REVIEW行为，不能宽免全部risk_unavailable。
可在现有missing/current-data场景插入fresh partial quote子步骤，不增加6方法/9DB及既定
撮合/分录预算：核无现金、cut保留、WAITING_DATA，再恢复完整fresh行情正常应用。

除此之外，产品周期/command跨kind幂等、NULL未知费率、准时可信writer cut、无cut迟到
不回填、frozen cash与current risk分离、原生监督器真实风险状态、SAVEPOINT及总事务原子性、
真实treasury原入金双分录与资本归属、proof唯一和reserve重放、状态查询/重启发现、互斥cap及
严格loaded artifact覆盖均在声明的有限假设内审清。九场景手算9匹配/18侧成交、8义务5已付
3未付、46journal、fee.72/custody-15001相符；真实101平仓后再应用旧100 cut，最终双方
999.91、费用.18，无虚构持仓或成交。

所有66个canonical regular物化输入共1,407,331字节逐Git及manifest核验；manifest
`fd71cf23615f115430737242bdbc5a36ae377be47f309ff6bd6a6427ede6f9cb`、manual plan
`375cb98c1290e14ab9a294938bb4edcb2a4399af360bba2398ca853e26fd79a3`一致。新模块59,799字节
SHA `6888454ecce7dbc5bb8e6a4201b75c005ce03aa7fb00ea0b290be9d6fdd1f513`。原62个其他UTA
模块不变，FundingLocal仅增加新旧cap互斥。审查使用Git/text/JSON/AST和独立人工算术，
没有把producer静态passed当作实际验收。

claim fence的验证点是在单SQLite writer事务内的最新_held/_clock观察。最后apply检查后仍
有receipt/task/command/event和COMMIT/fsync，不能宣称物理提交完成一定早于until_at，或
借此取得managed/HA保证；这不是本次新增的假设外硬时钟阻断。UTC、旧binary隔离和任意raw
writer排除均按原有限部署边界解释。

未来exact runner/6SQL/两个有界竞争线程均未授权。待付DUE尚未进入统一订单/提现/划转
预占、production timer、opsAuth/托管、旧binary真实fence、复制HA、故障/时钟/容量及金融
人审继续OPEN。修复后的新源码还须有限delta审查和独立风险cross；本审不授权生产启用。
