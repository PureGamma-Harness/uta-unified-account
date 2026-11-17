# M0 v5：四条已关闭原流 CMS 密文留存；仍待独立审查

本提交只实现 root 已选 option B，金融 workload 仍为 exact `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`，不启用 PR20、不执行 SQL/native/benchmark/Actions，也没有 M marker 或 push。deb3 与 b217 的原 49/75/83 PASS、独立首 8+4 RED 和后续源形状关闭均保留；b217 独立关闭 OWN `5f5b5ab615fbdec072ac5b2657f1cef60ba03933` 完整 pick 为 a325988。新的模式、预算及 SHA 必须由 root 重新审具体 C，旧批准模板不再有效。

## 精确范围与密钥边界

只对每个实际 case 的 `driver.stdout`、`driver.stderr`、`case-owner.stdout`、`case-owner.stderr` 四条文件留原字节。driver 为继承独立 case-owner session 的真实新子进程；frozen909 owner 返回且 leader 已回收、原 group 清理成功后，才认为生产者已关闭。case-owner 的捕获若曾截断仍加密已有前缀，并在认证 header 标 capture_complete=false、结果 UNKNOWN。缺失、未关闭、不可读或不完整不造完整。非零金融执行结果保持原 UNKNOWN，即使成功加密也不会重新变 PASS；后续 P 停止。

不宣称保存所有传递/native worker 的独立原流。SQL capability probe、crypto capability/helper 自身的 stdout/stderr 也不属于这四条金融 case 留存范围；这些操作失败只产生诊断 UNKNOWN，不能泛称完整所有子进程 raw。DB/WAL/SHM、原 request、交易 key/nonce/signature、整个 private 目录、二进制 pstats 均不打包。已有 profile 语义投影仍不等于原 binary byte archive。

只提交 root 提供的 public certificate 和 public metadata：PEM SHA256 `3140279eb39d7873fdcbd23fb46b71f987d43a12184087a791c5b2073b5f1fed`、DER `93e081eb110b196c355e0b6a3d91358ef530d7b8a98d6a3b392f47e64229c783`、SPKI `de01fcb8516224fd3d91f442899d582c4fcaa5aadfac8e91b45f680307ed3ab1`。实现与测试从未读取实际 workspace recipient 私钥；它不进入 Git、Actions 或 artifact。toy fixture 自产的测试密钥只留新0700私有目录，其私钥模式0600。

## 协议、精确字节与来源

采用系统 OpenSSL 3，无自写密码算法、无静默降级：

```
openssl cms -encrypt -binary -outform DER -aes-256-gcm -recip PUBLIC.pem \
  -keyopt rsa_padding_mode:oaep -keyopt rsa_oaep_md:sha256 \
  -keyopt rsa_mgf1_md:sha256
```

认证 plaintext container 为 `M0STREAM\0` + 4字节 unsigned big-endian header 长度 + canonical JSON header（最大4096字节）+ 原 stream 精确字节。header 内绑定 format=1、source909、C、controller SHA、run/attempt、case B/P、四选一 stream、recipient SPKI、capture_complete、原字节数和SHA256。header 和正文都在 AES-GCM 认证范围内。source 原流先有界hash，二次通过64KiB分块直接写 OpenSSL stdin，不创建 plaintext container 磁盘副本；核 inode/device/size/mtime 与复制摘要不变。空流同样封装认证。密文验证 DER 可解析，输出 file hash/fsync 后才入记录。

公开仅为固定目录下的 `.cms` 密文 bytes/SHA、公共 recipient fingerprint 与安全状态元数据，不公开原流SHA/正文或请求。GCM 是密文及绑定完整性；任何持公钥者都能生成密文，它不证明作者身份。执行来源必须由实际 GitHub run/attempt、exact C/M、上传 artifact ID/provider digest 和原平台记录额外闭合；controller 完成并不证明 upload 已成功或 artifact 已持久可取。

runner 在金融 driver 前先用固定公开合成短流证明其实际 OpenSSL 版本/二进制SHA、公cert PEM/DER/SPKI、AuthEnvelopedData/AES256GCM/RSA-OAEP-SHA256 均可用。它不使用 private key。这里本地 OpenSSL3.5.7 已验证，未来 ubuntu-24.04 的实际版本仍必须在原首次 run 验证，不能跨机声称兼容或比较性能。

## 原始首失败、独立预算与输出发布

金融 case pipeline 的独立 owner56秒+TERM2+KILL2及完整case≤60秒检查保持。其后另起独立 escrow owned session，20秒+TERM2+KILL2，覆盖4流hash/流式加密/DER检查/fsync/原子发布；这个额外阶段计入 job6分钟，不混为金融完成延迟。每条完成先将安全metadata journal fsync，再原子公开该完整密文；以后流失败仍保此前密文。父控制器即使 helper UNKNOWN 也收集已journal+发布的完整密文。未完成/损坏 cipher 与 OpenSSL stderr 留 private，不在白名单中。helper 自身进程故障、文件系统不可写、宿主销毁或 artifact 上传失败都可能使证据不完整，结果保持 UNKNOWN；不承诺 crash RPO 或灾备。

root 明确授权新格式预算（原未执行旧合同留 Git 历史）：normal authority/workload 每case32MiB、总64MiB；strict streams-only cipher escrow96MiB；cleanup32MiB；逻辑总≤192MiB；另需2GiB fresh余量，`MIN_FREE=2,348,810,240` 字节。四分量及时独立检查；只允许固定四流 `.cms` 及命名metadata占 escrow，放 DB/任意文件会拒绝。超过任一门槛 UNKNOWN 并停止P。旧 `2,214,592,512` 字节保留为 LEGACY_MIN_FREE 与旧原报告，不重标旧性能。所有门槛都是逻辑观测，不是 OS quota、磁盘最坏IO、空间过量分配或物理硬实时保证。workspace原19,662,897,152字节cohost预算未变。

new once manifest format=2、kind=ROOT_REVIEWED_ONCE_M0_V2_ESCROW，绑定新的 controller/workflow/escrow tool SHA、public recipient SHA/SPKI、versioned command/budget、C→sole marker child M。只有 root 明确审定后的一次专用分支 creation push 才可触发；当前模板仍 execution_authorized=false/C全0。safe upload 仍须完整 manifest、固定目录/文件名、无symlink/special/extra，新增仅 `.cms` 白名单；绝不对 private 目录 glob。

## 离线认证解密与本次证据

`decrypt_authenticated` 只作为 offline helper：调用者提供其私钥路径，新建0700 quarantine，OpenSSL stdout 写新0600 unaccepted-container；必须 decrypt returncode0 后，才解析完整 header 并核所有 expected binding、长度和原SHA。认证失败即使产生输出也不解析、不接受、不公开。通过后仍留 private，函数仅返回校验元数据。

本地真实 toy fixture 初次279字节，认证roundtrip和协议结构PASS；tag改位失败实际写了799字节未认证容器，保持 private/unaccepted；截断、wrong-run binding均拒绝。实际root public cert加密成功，root独立在其私有域解密并核 body hash。仅 root 明确允许复制的 public observation 在 `escrow-root-decryption-first.public.json`；私钥、解密容器与stderr未读取/复制。最终新增源码版本另保存 tiny fixture 原结果，不覆盖首件。纯测试还覆盖不启动OpenSSL的PREP、绑定复用、hash/trailing/header cap、symlink、失败解密绝不parse、4流精确映射、单流失败留其余3条、严格资源分项及manifest。

本次无金融负载/SQL/native/profile/实际 Actions。首次纯98项中1个失败是 upload 测试仍按旧单行YAML定位；修为多行path检查并保首RED。扩展102项中的首失败是fixture将自身plaintext放进待验证public目录，strict manifest正确拒绝；改隔离fixture目录，原错误原件不删。完整最终源码SHA/命令/时间/原stdoutstderr另有execution record。以上仅限代码/纯控制与小合成crypto，不证明生产、10k/s×30min、真实清算成交、HA、远端M0或artifact durable资格。

回滚：不登记/不push M；root可回退控制候选或新提交修复。发生实际首失败时保原run/原cipher/原UNKNOWN，不rerun覆盖。source909、old jobs、真实金融权限不部署不迁移。
