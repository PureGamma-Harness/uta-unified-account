# e7a1b3e 独立协议关闭：限定组件通过，执行权不随审查产生

固定C：`e7a1b3ee22a957350359463da60b99d9df6c589a`。escrow module SHA-256：`89f48b50d22a1b8c5898ed9413ad6bc2567f6cd30c0a58626d0921f5e91ec83e`；controller：`6c5656dc45a8648aff8e309f2d082f9d3e4af5f456acaeeaed4d5be447a176af`。结论为 **PASS_SCOPED_STRICT_CMS_PROTOCOL_CLOSURE**，整体仍 **NO_GO**，没有实际M0、Actions、SQL/金融native、marker、push或生产授权。

旧5d/c617的CBC和OAEP-SHA1首RED原样保留。此次不是重新生成近似反例：从c617不可变保留记录取得原两份cipher文件，先核实际SHA与原件相同，再交新helper拒绝。旧cipher中5d的binding只用于重放历史输入；没有把它们当成新C产生的证据。

## 最小实际复核

CPU3、外部15秒watchdog、原文仅129字节；`20:03:27.681415–20:03:27.758829 UTC`，77,415,624ns，首次exit0。沿用本reviewer先前自产的toy recipient/key，核对原key/cert摘要；没有读取实际root私钥或旧未认证plaintext，也没有复制任何私钥。所有新fixture和cipher原件留在新0700私有目录，公开只有安全结果与摘要。

- 原CBC EnvelopedData/PKCS1v1.5和GCM/OAEP-SHA1两份原cipher均在decrypt、container parse和quarantine创建前拒绝；两个入口调用计数为0。
- 新C新生成的AuthEnvelopedData/AES256GCM/OAEP-SHA256/MGF1-SHA256正例真实加解密通过，129字节原长度与SHA一致，nonce12/tag16、单recipient、无attrs元数据正确。
- 新MGF1-SHA1实际cipher拒绝；trailing、truncated、indefinite、nonminimal length、错误ContentInfo OID五个DER canary均拒绝。
- 坏tag的DER仍可正确判为协议形状合法，但实际GCM认证失败；保留648字节未认证输出，parse调用为0，未读取其内容。错误run binding在认证后拒绝。

十一项控制零RED；原stdout/stderr、代码和原cipher摘要见 `review-manifest.json`。没有重跑作者旧102/108套控制，也没有用其279字节正例替代本次独立原降级输入。所有实际crypto只使用自有toy，未执行工作负载或实际远端操作。

## 代码与范围判断

小型DER reader按结构/OID和exact-end解析，不用文本contains判型；对文件32MiB+64KiB、depth16、nodes256、结构value16KiB有界，较大ciphertext按offset跳过。只接受当前窄profile：精确AuthEnvelopedData、version0、单KeyTrans、显式SHA256和MGF1-SHA256、nonce12、ICVlen16、mac16；拒默认SHA1、额外字段/attrs和非canonical长度。它不实现密码算法，真正加解密和tag认证由OpenSSL完成。

该版本故意只接受已审OID-only SHA256 AlgorithmIdentifier，拒NULL等可能等价编码；本地通过不是普遍CMS或未来Ubuntu版本兼容证明。首次远端capability必须实测实际OpenSSL编码，不兼容时UNKNOWN，不能自动降级。

出站seal、offline入站、capability及public cipher manifest共用协议validator。public侧没有私钥，因此格式通过不等于GCM tag认证；仍须由离线持key方在成功认证后核完整source/C/controller/run/attempt/case/stream/recipient/capture/长度/SHA绑定。公开recipient仍不认证sender；实际provider C/M/run/attempt/artifact ID/digest来源链不能省略。

对比5d，controller唯一变化函数是 `verify_public` 增加cipher协议验证，其余四流、journal、UNKNOWN和资源函数AST一致，可结合 `ed601cf659c960b19ff814c8fddf3a3bc9e25cf1` 的独立纯流控证据。该证据仅为纯桩，不证明真实PID清理、上传持久获取、宿主故障RPO或磁盘硬实时。normal64MiB/escrow96MiB/cleanup32MiB与fresh2,348,810,240字节不变；financial≤60秒与独立escrow20+2+2是不同阶段，不能说完整发布≤60秒。

只有driver/case-owner四个已关闭原流在本范围内；不是所有转发native流、DB/request/key/nonce目录、probe/helper流或profile binary的完整raw归档。实际artifact可获取、离线认证解密及其原字节核对仍须在首次真实获批run结束后完成。

本OWN是独立review，不是新execution C。若把review合入控制版本，应重新pin C/M及manifest/hash，不能默认为旧审批延伸。root仍需审具体登记与最终GO；本报告不创建或推送M。所有旧首失败、source909和原作业保持不变。

本提交仅新增review脚本、合成证据和说明，无运行时/API/数据库部署或迁移；撤销review提交即可回滚工作树，原件与首失败必须保留。
