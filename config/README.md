# 合成配置

`synthetic-products.json` 与 `synthetic-risk-rules.json` 由 `uta.examples.synthetic_policy()` 生成，只用于隔离测试，不是实际交易所参数或真实资金启用许可。USD 是合成报告/结算币；BTC 数量和资金来自合成或明确授权的本地记账。

```sh
python -m uta exchange --database /private/uta/authority.sqlite3 \
  --credentials /private/uta/credentials.json \
  --asset-scale USD=8 --asset-scale BTC=8 \
  --catalog config/synthetic-products.json \
  --risk-rules config/synthetic-risk-rules.json --automate
```

凭据文件按运行手册单独生成，不复制真实密钥到此目录。新库默认暂停。行情必须由获授权的风险操作者发布；示例配置不会接入实时价格。借款还需明确资金池和账户/资产限额，没有默认自动授信。

产品与规则作为同一个版本组合保存，重新打开数据库必须携带相同配置。禁止删掉参数来降级成 legacy 模式，不能直接覆盖 JSON 使已有数据库接受新费率。正式风险参数审批、影响试算、灰度与回滚尚需控制面验收。

`--automate` 启动有界风险监督和本地真实对手订单撮合；不生成标记价成交，不连接外部账户，没有流动性就保留待成交订单。账户调度游标可恢复，权威状态仍由每个本地事务保证。跨可用区复制、生产 PM 和万笔验收没有因此启用。
