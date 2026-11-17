# 最终公开控制候选C：仅PREP

完整合入独立组件证据：四流/预算OWN `ed601cf659c960b19ff814c8fddf3a3bc9e25cf1` 与strict CMS closure OWN `5622305ea99e2c2450aaacf5d28e9d3e949fd10d`，原c617首RED、所有fixture首FAIL及错误cwd/NameError原件均保留。控制器、加密模块、fixture工具和两个workflow保持e7a1已审字节，不重新运行crypto、金融或CI。default template仍execution_authorized=false/control_commit全0。

source固定909；62 runtime的Git subtree为 `5ab19a2bb5d3b66a6cc2b60ae1fb1e2239ab1c4b`，内容SHA256映射聚合为 `ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b`，完整source Git tree为 `cee60bc0b5413551030300e065d0dcaac6a7ff55`。此处不以Git SHA1树与内容SHA256混用。B/P确切argv模板、V2正常64MiB/密文96MiB/清理32MiB/fresh2,348,810,240字节、recipient PEM/SPKI均在defaultfalse模板中固定。

可重跑的只读公开检查：

```
python -B docs/evidence/independent-actions-m0/final-publication-check.py \
  --candidate <exact-C> --output <new-safe-report.json>
```

它读取Git/files，逐项证明相对source909只新增已声明控制/docs/evidence文件、runtime62不变，列exact diff每文件OID/bytes/SHA，扫描新reachable history的每个blob，包括已替换/删除旧版本。检查private-key PEM材料、常见credential token及signed URL模式、非UTF8和禁用载荷扩展。source909以前的公共祖先历史不在本新增公开审计范围；模式扫描不证明任意文本绝无秘密，仍需按合成fixture/publiccert/安全摘录范围人工核验。不会读取workspace私钥或原未认证quarantine明文。

最终C的扫描报告和只供root审阅的PROPOSED marker放在Git外的独立review目录，避免C自身SHA与自己的report互相引用。marker由defaultfalse模板复制，填真实C/source/控制及recipient哈希、fresh workspace boot/hostname参考；execution_authorized=true只代表提案内容，文件不在literal config路径、不入M、也没有触发分支/push。checksum或JSON旗标自身不给执行权限。root必须独立审完整C与marker，且由root最后决定是否创建sole manifest child M及精确一次push。

PR22原3.11恢复错误详见 `docs/independent-actions-m0-known-issues.md`，始终构成生产/容量/可靠性NO_GO。即使以后特批一次M0也只合成低量诊断，不能覆盖原error、旧firstRED或假称生产。原workspace预算/source/旧新长作业不动。
