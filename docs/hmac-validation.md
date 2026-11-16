# Durable HMAC 协议的独立防御性验证

本报告审查冻结基线 `f1f3e89` 上的签名增量 `6eecb38`、`79efff6`、`f22bd07`。独立组只新增 `tests/test_hmac_reference.py` 与本报告，不修改运行时，不使用真实密钥、客户数据或外部交易所。当前已验证范围未发现需要阻断该候选继续工程审查的已确认协议差异；**G7、生产与真实资金启用仍为 NO-GO**。

## 范围与信任边界

逐项阅读了两个变化中的运行时模块 `uta/request_signing.py`、`uta/durable_gateway.py`，沿调用检查原有HTTP framing、Credential角色/账户边界、持久队列与Database提交行为；同时核对变化中的签名测试、durable gateway测试及两份接口文档。这是签名入口的局部审查，不是全仓安全审计。

对手模型包括未认证客户端、拥有账户A合法密钥的客户端、跨tenant/audience重放、重复/变形HTTP字段，以及同时访问同一认证库的多个HTTP进程。故障模型包括进程重启、丢HTTP响应、认证COMMIT失败、认证schema guard缺失和认证文件丢失。本机OS用户、密钥生成/保管及证书发行环境仍可信；未将本机SQLite认证库解释为跨主机重放共识或外部防回滚见证。

安全差异审查技能说明已读取，但本环境缺少其专用扫描工具、本地helper及可读的附属preflight资源，因此没有完成该专用扫描协议，也没有生成或宣称Codex Security完整扫描、SARIF或自动认证。以下结论来自人工变化审查与实际独立测试，保留这个工具覆盖缺口。

## 独立客户端与真实TLS

测试客户端用标准库 `json/hashlib/hmac` 自行构造协议数组、原始body摘要与MAC，**不调用生产 `canonical_request` 或 `sign_headers`** 来生成预期。HTTP请求、TLS握手、nonce接纳、入队和金融结果均不mock。

每项测试实际生成只供该测试使用的自签证书，SAN明确包含localhost/127.0.0.1；客户端只信任该测试CA，启用 `CERT_REQUIRED` 与hostname校验。未信任该CA的真实客户端必须证书验证失败。服务器最低TLS1.2，原始wire请求也经过实际验证的TLS。缺少openssl会明确失败，不用skip消除TLS覆盖。

签名服务的epoch-ms时钟在测试中是可控输入，用于精确窗口与跨重启断言；行情使用真实当前合成观测时间。此设计不构成NTP运维、真实密钥生命周期或公网证书体系的验收。

## 九项实际回归

```sh
python -m unittest discover -s tests -p test_hmac_reference.py -v
```

| 场景 | 必须保留的观察 |
| --- | --- |
| TLS、domain与权限 | 未信任证书的客户端失败；即使使用正确secret重新计算MAC，错误tenant或audience仍401；跨账户与reader下单403，不入队；Bob不能查询Alice回执，普通trader不能读risk metrics |
| 重复header/framing | 八种签名header分别在真实TLS wire上重复，全部拒绝；Authorization由既有framing返回400 duplicate_header，其余签名字段401 signature_required；重复Content-Length返回400；nonce与队列均为零 |
| 精确签名内容 | 改body一个空格、改method或raw target均invalid_signature；无效MAC不消费nonce，原exact请求仍可用该nonce恰好入队一次 |
| 真正丢TLS响应及HTTP PID重启 | 客户端发送完整请求后不读取响应；观察到实际PENDING再重启真实HTTP子进程；旧nonce409，新nonce+原CID恢复同一sequence；随后真实fenced writer仅接纳一个订单，占用手算10.04USD |
| 旧进程与撤销/profile回滚 | 新profile在共享库撤销Alice后，仍运行且持有旧内存profile的TLS HTTP进程立即拒绝该key；低revision加载及更高revision试图复活旧ID均拒绝，持久revision和revoked值不回退 |
| 两个独立TLS HTTP PID竞争 | 同一个签名/nonce并发发往两个真实子进程，只出现一个202与一个409；认证库恰有一个nonce和一个nonce_consumed事实，队列恰一条 |
| 真实认证COMMIT失败 | 真实deferred FK触发器在auth_nonces插入后使外层COMMIT失败；HTTP503，金融队列、nonce及nonce_consumed审计均无新增；移除故障后原请求同nonce可入队一次 |
| schema损坏与文件缺失 | 删除真实认证完整性trigger或移走认证文件均503；不自动重建，不入队，也不回退Bearer/内存authority |
| 精确nonce期限与时钟高水位 | 最老可重放边界仍保留nonce并拒重复；再过1ms清理后旧请求按窗口拒绝；将时钟退回并重建authenticator仍503 clock_regressed，不能复活旧签名 |

最后一次执行：**9 tests，0 failures/errors/skips，2.232秒**。环境为Python3.12.14、SQLite3.53.1、OpenSSL3.5.8。测试中的多个HTTP PID确实不同于父PID，不以内存Future或同一线程模拟跨进程。其中金融验证仅证明既有订单准入与幂等，没有生成或计入撮合吞吐。

初次执行中的两个失败来自测试fixture：Authorization重复由原HTTP framing更早按400拒绝，测试最初只预期401；另一个fixture错误使用会隐式COMMIT的executescript，被Database正确拒绝“caller ended managed transaction”。现分别核对原有明确拒绝code、用逐条DDL安装真实提交故障，未修改运行时、放过重复header或降低金融断言。修正后完整运行通过。

## 审查结论与明确限制

当前路径的关键次序为：验证精确MAC，取得认证事务锁后采样时钟，持久提交nonce/认证审计，再执行角色、路由与enqueue。nonce已消费、202已排队、终态金融接纳是不同事实。丢响应后客户端必须用**新nonce、原账户/CID与原业务内容**查询或重试，不能把nonce当CID，也不能换CID盲目重做。

profile低revision与已撤销ID的重新启用被拒绝，属于应用协议的防回滚；它**不证明**由可信OS用户在相同路径恢复整份旧认证库、克隆机器或回滚金融库后仍能阻止所有历史重放。该部署绑定在factory启动时核对实际producer；本次没有验证运行中替换整个金融authority文件、外部全局见证或跨主机nonce复制。

没有覆盖KMS/HSM、硬件密钥隔离、真实密钥轮换值班流程、网络代理/TLS终止、DDoS/长时并发容量、形式化密码协议证明、第三方渗透测试或完整多租户部署编排。单个入口绑定一个tenant和producer；risk/admin仍是该tenant内部的权限，不能被解释为跨tenant授权。认证库磁盘满、nonce/audit增长与长期时钟运维还需要专门容量和故障演练。

结论是允许该有限候选继续审查；没有签发生产安全、金融规则或真实资金批准。专用扫描缺口、上述部署边界与正式独立安全签批仍保留，生产状态继续 **NO-GO**。
