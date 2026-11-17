# 5d4b5c7 独立CMS审查：入站协议降级未拒绝

**首个硬阻断：NO_GO。** 固定C为 `5d4b5c7cb02ff3c365532e16faead233093faac9`；escrow模块SHA-256为 `e894ba1c5b7c6370744dad09b9cfd7b008b0cc0002807275deaf6f9bc2d4bc9f`。当前 `decrypt_authenticated` 将通用 `openssl cms -decrypt` 的退出0当作认证前置，但没有先要求已批准的AuthEnvelopedData/AES256GCM/RSA-OAEP-SHA256/MGF1-SHA256协议。

这是入站协议契约违例，不是已经发生的金融攻击。公开recipient加密本来就不认证sender；GitHub实际C/M/run/attempt、provider artifact及其digest的来源链仍须独立核验。本次反例没有证明可以伪造这些provider来源记录，也没有接触真实资金或实际root私钥。

## 首次实际小合成反例

reviewer在新0700私有目录自产一对2048位toy key/cert，私钥0600。CPU3外部15秒watchdog内，于 `19:46:21.968653–19:46:22.189678 UTC` 完成，221,024,894ns，原文仅129字节。所有私钥都属于本次自有toy；实际root recipient私钥从未读取。没有SQL、金融native/M0、profile、Actions、登记M、push或子Agent。

- 正常模块生成的GCM/OAEP-SHA256封装：成功认证解密，原129字节长度和SHA一致。
- 反例一：用相同有效M0STREAM container、binding和body构造普通CBC EnvelopedData + PKCS1v1.5。OpenSSL结构明确是 `pkcs7-envelopedData`、`aes-256-cbc`、`rsaEncryption`；helper仍接受，返回 `binding_valid=true` 和 `authenticated_decrypt_exit_zero=true`。CBC的解密退出0不是GCM认证成功。
- 反例二：GCM但显式OAEP-SHA1/MGF1-SHA1。helper同样接受。DER的OAEP参数为空SEQUENCE（默认参数），不能因为输出中没有sha1字面值就误称它是SHA256。生成命令和结构片段均保留。
- 正常GCM tag改位：helper正确在parse前拒绝，实际产生648字节未认证输出，parse调用为0；未读取或解析该失败plaintext内容。错误run binding也正确拒绝。

第一批原stdout/stderr保存在 `crypto-first.*`，两个首RED未重跑改绿。`cms-protocol-excerpts.json` 保存结构依据；`private-toy-retention-manifest.json` 仅保存自有toy文件的名称/大小/权限/摘要，不复制key、plaintext或二进制。quarantine的unaccepted plaintext仅记录大小，没有再次读内容做hash。原fixture、密文和首失败私有文件全部保留。

## 最小修复复核门槛

入站在任何decrypt/容器parse之前必须拒绝未批准CMS content type、cipher、key transport及digest组合；成功解密不能替代协议检查。输出发布前的DER检查也应验证该精确协议，而非只要求“任意CMS可解析”。仍须在认证失败时不parse、不接受OpenSSL可能写出的部分plaintext。

下一固定revision须保留这两个首RED，证明相同CBC/OAEP-SHA1输入拒绝、正常精确协议通过、badtag/错误recipient/错误binding仍拒绝，不得用此前已知GCM密文的单个bodyhash正例代替降级反例。review未修改作者实现。

## 四流与预算追加纯控制

四流/预算helper首次在最终模块检查因reviewer漏import sys而失败，`flow-first.*` 原件保留。只补helper导入后，第二次CPU3于 `19:57:31.703969–19:57:31.784071 UTC` 完成，80,124,696ns，exit0，controller过程入口零调用。该次未运行OpenSSL、SQL、金融native/M0或Actions，也未读取任何私钥。

本次从固定C抽取纯shape fixture，并用独立断言观察实际helper的journal和原子publish顺序：

- 完整4流严格映射为driver/case-owner的stdout/stderr；每个cipher原子公开前，已fsync的journal包含同名/同SHA记录。
- 分别令第一、中间和最后一流失败，其余3条完整cipher都保留，源流不删，整体UNKNOWN；不造4条完整结论。
- case-owner捕获为prefix时4个已有cipher仍保留，但结果UNKNOWN，不能升格完整捕获。
- normal64MiB、escrow96MiB、cleanup32MiB和192MiB总和等值允许；每个分量+1拒绝。大字节边界用lstat纯桩，不分配大磁盘文件。fresh门槛确为2,348,810,240字节，旧2,214,592,512原记录保留。
- 无producer关闭证明时，在加密owner/crypto之前拒绝。

公开路径按已固定controller限制在安全JSON和4种cipher文件名，拒symlink/special/unlisted及伪装DB文件名；这不等于对任意JSON payload已完成通用隐私证明。实际writer只输出已审投影/安全状态，原key/nonce/request/DB或整个private目录不进入upload。必须结合固定C/provider来源链，不能把checksum或recipient加密本身当sender认证。

financial case≤60秒与其后的escrow20+2+2是不同阶段，不能称所有发布≤60秒；实际OS清理、远端文件系统、artifact持久获取和first-failure物理存续并未由这些纯桩证明。四流范围不扩大到所有转发native独立流、SQL/crypto probe或helper自身流。

这些流控/预算纯控制通过没有关闭上文两项协议RED，5d4b仍NO_GO。后续strictDER新固定C须另行实际小合成复核，不承接这里未验证的密码协议或真实M0资格。没有root实际执行GO。

本提交只增加独立review、合成probe及证据，无运行时/API/数据库部署或迁移。回滚为撤销review提交；旧C、所有首RED、私有toy原件、source909及原运行任务都须保留。
