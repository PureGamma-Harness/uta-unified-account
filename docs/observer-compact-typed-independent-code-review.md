# Compact-v2 类型边界修复：独立 CODE 审查

固定修复 `1c7b836a51dd4387013fdbf7186491e408be9f25`，首证据 tip `951b99851775a239e25f4350e0cb1e5c2a4ef2c4`。**已知四项 JSON 类型别名 finding 按 CODE 关闭；原 e497 的四项独立 FAIL 和全部首次证据保持不变。** 本次没有执行新旧测试，不能替代实际 watch、文件系统或长测验收。

## CODE 结论

publication 与完整 compact 的比较改为 canonical JSON bytes；重算 summary 与原 publication 的比较也采用相同方式。有限普通 JSON 域下，`1`、`true`、`1.0` 的 bytes 不同，四项已知反例不能再通过 Python 数值相等性混淆。protocol、array node 和 full-reference node 的 version 均要求精确 int，`2.0` 不再等价于协议整数 2。

`canonical`/`fingerprint` 先限制输入为普通 dict/list、字符串键、null/bool/int/string 及 finite float。`_read` 使用拒绝 duplicate key 和 NaN/Infinity 的 parser，并继续核查 canonical bytes 与原 CAS bytes 相等。合法 JSON 中的整数、浮点与布尔值仍可以完整还原，不能用“统一转成某种数字类型”修复别名。

上述范围没有承诺任意深度输入的 total parser、Python 自定义对象或 tuple 兼容性。`_json_domain` 仍递归；超深数据的结构化拒绝和硬资源限制不在本次已验范围。原 2KiB/item、64 层、64KiB/full-reference node 和16KiB compact 导出域限制保持，不能解释为覆盖了所有 legacy 输出。

## 已有首结果的独立来源绑定

新 codec SHA `ae81dc4140cb7fdbfc00ed7937267b7897d050f5fee73257cbb373739d0154b1`、focused test SHA `cb3988f56b58d3ff3d8caa744dd0a38054a5df2dcc003ea81233e69bcdbd8e50` 均与预执行 plan、修复 commit 和首证据 tip 相符。首 stderr 明确八项 `ok`、8 tests/0.009s/OK，execution 记录 exit 0。五个原始文件合计2,535B：source-plan 887B，加 inputs、start、stderr、stdout 共1,648B。

逐字节比较确认旧独立 evidence 7 个文件与 `2d8e77201b6274f4bcb13e4098af1c21bd638660` 相同，旧作者首批 evidence 6 个文件与 `00989ce23bd0db5d03485626ea6fa9693fc4e508` 相同。typed 修复不改变冻结 runtime tree 或原 coverage 主体。本次未重跑作者新旧八项或独立八项。

审查初期的两个元数据小探针错误也保留在 [绑定记录](../evidence/reviews/observer-compact-typed-code/code-and-raw-bindings.json)：第一次错误地把2,535B解释为不含 plan 的四原件总量；第二次抄写 baseline SHA 漏字符。更正均为只读 Git 元数据核对，没有执行目标测试或修改候选证据。这些不是候选回归。

## 仍未通过的门槛与回滚

focused 中的“安全动作”是合成回调 marker，仅证明其调用次序；没有实际 financial drain、进程、SQL 或落盘测试。API 仍未接入 watch，DirectoryStore 实际 FS 未执行，真实2GiB输出治理、恢复、覆盖率与六小时稳定性尚未验收。producer、full consumer、classify_safely 回滚及已知 fatal drain 必须先完成，export UNKNOWN 不得吞掉已有金融告警，也不得重复消费同一 attempt。

本 OWN 仅新增文档及绑定记录，无服务、schema、参数或原数据变更。回滚只移除本 OWN 新文件；原 e497 首 PASS、独立四 FAIL、新 focused 首结果、旧运行 NO_GO 及所有私有输入应保留。生产和真实资金批准仍为 false。
