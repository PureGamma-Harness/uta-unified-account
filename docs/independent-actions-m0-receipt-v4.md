# M0 v4：按持久拒绝回执原错误核业务/控制分类

deb3fc56 的原 8 反例关闭后，独立组在 `5f365f22d11a1851042789420e9755483f0c4b21` 新发现 4 个实际纯 RED：business 标签搭配 error.status=503、control 标签搭配 400、拒绝 error 非 JSON、error 缺 status。该 OWN 完整 cherry-pick 为 3988cee，所有首 RED、原 8 关闭与 source/hash/adapter、原始 stdout/stderr 均保留；deb3 继续 NO_GO，没有追改旧 75 PASS。

source909 `benchmarks/run_managed_benchmark.py:134` 的 terminal_outcome 以解析后的 error.status<500/≥500 分业务及控制拒绝；`uta/durable_commands.py:381` 的真实 error 为 `{code,message,status}`。新 parser 对 REJECTED 要求 dict 或 strict JSON object 的精确三字段、字符串 code/message、exact int status 100..599，拒 bool/float/NaN/Inf、重复 key、缺字段及不符 outcome 的类别。SUCCEEDED.error 必须明确为 None。只投影数字 status，不公开原 error code/message。跨人口统计和原 gzip/watchdog 规则维持。

最初独立原两正例省略 error，属于当时 parser 的部分形状正例，现已不足以满足完整 source909 receipt 契约。新的完整参考夹具仅补正常 error=None 或 400/503 +code/message，原 8 变异语义不变；第 8 项金融→业务时同时给合法400拒绝错误，使拒绝仍由跨文件人口不符触发。旧原两正例 PASS 历史与四首 RED 字节不改，不假称未经补形状的输入仍通过。

新增 8 个纯测试后共 83 PASS，最终 source-bound 命令、代码/测试 SHA、时间、完整 stdout/stderr 见 `docs/evidence/independent-actions-m0/receipt-classification-execution.json`。独立组仍须对固定新 C 检查原 8+新 4、正确完整正例及类型边界。没有实际 SQL、产品导入、native、profile、Actions、push、M marker。此提交不包含另行开发的 CMS 工作树文件，privacy 仍为 private ephemeral R&D-only；必须等 option B 与独立审查后才讨论实际 M0。

回滚：保持不登记/不 push M；新问题另提交与留首 RED。source909、旧任务及真实金融权限不变。
