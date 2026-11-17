# 只读历史连接路径归因

分析源基线为 adadffc，金融数据来源是既有 corrected720 P1 profile。
没有新 SQL、负载、服务或性能实验；金融 runtime 零 diff。

```sh
python tools/analyze_connection_profiles.py --output /tmp/new-connection-attribution.json
cmp /tmp/new-connection-attribution.json evidence/runs/connection-profile-attribution/attribution.json
```

脚本先校验原 manifest/profile SHA，派生 JSON 保留完整 SQLite caller 边和来源。
角色计数为明确假设下的 generator resume 估计；各角色耗时不能由此精确分摊。
两个 child self>cum 为0，parent 为5，父耗时排除。没有生成 performance pass。

结果与不实施 session 的理由见 [归因记录](../../../docs/connection-lifecycle-attribution.md)。
本目录不复制或改写原始 profile，也不包含 authority、私钥或新的金融结果。
