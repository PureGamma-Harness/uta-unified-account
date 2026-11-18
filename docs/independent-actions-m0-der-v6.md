# M0 v6：精确验证 CMS 算法结构，再接受认证解密

独立 OWN `c617134f648bf4a79af2742e87fd96073d232428` 完整 pick 为 add23f4，保留5d4b的102 PASS和首次两个实际crypto RED。它们证明旧 offline helper 错将 generic `cms -decrypt` 返回0等同于约定协议认证：正确绑定容器使用 CBC EnvelopedData/PKCS1v1.5 或 GCM/OAEP-SHA1 时都能被旧 helper 接受。这是未启用候选的入站协议契约错误，不是已部署金融攻击或实际root密钥泄露。原始工具、raw、DER观察和toy私有保留metadata不改。

新增小型有界 DER reader 只识别本系统当前seal profile，不实现密码算法或通用ASN.1库。加密、解密及真正GCM认证仍由系统OpenSSL处理。共用 `validate_cms_protocol` 用于出站seal、offline解密前置、runner公开recipient capability和公开artifact manifest校验；不再依据打印内容contains判型，也不依据通用decrypt返回0判协议。

严格结构依次为：ContentInfo exact `id-smime-ct-authEnvelopedData` OID，explicit [0] AuthEnvelopedData version0；恰好1个issuerAndSerialNumber KeyTrans recipient/version0；RSAES-OAEP；参数[0]为SHA256 AlgorithmIdentifier、[1]为MGF1(SHA256)，无省略回退SHA1、无额外pSource；encrypted-key为受限RSA大小；contentType为data，AES256GCM参数nonce12字节、显式ICVlen16；primitive encryptedContent；mac16字节；逐层exact-end。originator、authAttrs、unauthAttrs、额外recipient/fields、尾随数据、BER indefinite和非最短长度全部拒绝。Issuer Name仅作有界已知X.509字段类型/长度/SET排序检查，不解释其文本为算法配置。

SHA256两个AlgorithmIdentifier窄匹配本地OpenSSL3.5.7实际生成的OID-only参数缺省DER（源码常量给精确字节）。NULL参数等其它可能等值编码此版本也拒绝；没有默认算法或静默兼容分支。不宣称普遍CMS兼容，Ubuntu实际编码仍须首次remote capability gate验证；不能把本地通过当远端已通过。将来放宽必须新来源、canary、C与独立审查。

DER输入仅regular/no-symlink文件、最大32MiB+64KiB；递归深度≤16、节点≤256、累计读取的结构value≤16KiB、issuer≤4KiB及受限每字段长度。较大密文和encrypted-key只按有界offset跳过，不整文件展开。验证格式不等于已验证GCM tag或作者身份；offline仍须OpenSSL认证返回0后核完整container binding/长度/SHA，origin仍靠实际provider/C/M/run/attempt/artifactdigest闭合。

新增纯canary覆盖外层CBC OID、OAEP-SHA1、MGF1-SHA1、未批准SHA256 NULL编码、nonce/tag长度、attrs中伪装算法字节、尾随/indefinite/nonminimal DER。公开artifact即使cipher SHA完全匹配也拒绝协议错误。纯测试用明确“不具有效密码学MAC”的结构夹具，只证明格式门槛，不假称其完成认证。解密协议拒绝发生在OpenSSL与plaintext quarantine创建之前；坏GCM tag仍保未接受的私有输出，不解析、不公开。

已授权新279字节toy、CPU3/15秒外限下：正确协议roundtrip PASS；原CBC与GCM-OAEP-SHA1以及新增GCM-MGF1-SHA1在plaintext创建前拒绝；坏tag留下799字节私有未接受输出，未读其内容；truncated在DER bounds先拒；wrong-run绑定拒绝；actual public cert仅encrypt，不读actualroot私钥。第一批最终FAIL是旧fixture假设truncated总生成quarantine并stat缺文件，原first raw保留；只适配为 `cms_der_bounds` 且无quarantine，不改原协议攻击变异，第二新目录完整PASS（234.9ms）。两批原始stdout/stderr及各源码SHA/命令均在 `der-profile-crypto-*-inputs.json` 等文件，不重跑覆盖。此前独立原129字节首RED保持原字节。

金融/资源/执行边界同v5：normal64MiB+escrow96MiB+cleanup32MiB，fresh2,348,810,240字节，金融case56+2+2/≤60s及独立postcase escrow20+2+2不变，无OS quota/硬实时/HA承诺。新controller/escrow/template SHA必须重新审定；没有actual M0、SQL/native/profile、Actions、push或M marker。当前NO_GO，待独立验证对固定新C关闭原RED并审整体范围；没有生产、10k/s×30min、清算成交或durable artifact验收资格。

回滚：不登记/不push M，保留所有首失败与旧C；新问题另提交。不改source909或旧作业，不读取实际root私钥和原quarantine明文。
