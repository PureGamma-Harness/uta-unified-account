# 离线部署声明与路径角色检查

`tools/check_deployment_manifest.py` 在启动现有服务之前检查一份严格版本化声明及
它引用的文件元数据。它补充 `deploy/README.md` 的人工准备步骤，不替代已有
`uta-durable` 预检、TLS/签名配置校验、安装包检查、迁移和真实恢复验收。

检查器只允许声明合成 USD、Cross、现货与受限线性永续的单 Linux 主机审查环境。
这里的列表是审查范围约束，不证明某交易对、乘数、参数或产品组合已获准上线。
USDT/USDC 结算、PM、Isolated、期权、反向、交割及跨主机复制声明均拒绝。

## 使用与错误契约

从 `deploy/review-manifest.template.json` 复制到一个新的本地声明路径。模板故意
保留全零 artifact digest，原样执行必须返回 `artifact_digest_uninitialized`，不能
直接成为可用部署配置。填写独立校验过的实际发行版 source/artifact/rules 引用、
专用非 root 服务 UID 和已准备好的角色路径后运行：

```sh
python -B tools/check_deployment_manifest.py --manifest /absolute/review-manifest.json
```

退出码0只表示 `REVIEW_DECLARATION_AND_METADATA_CONSISTENT`；退出码2为拒绝。
输出稳定错误码，不打印输入内容、密钥、签名、nonce 或任意系统错误路径。未知字段、
重复 JSON 字段、未初始化引用、布尔冒充 UID、引用不一致和自称真实资金批准均拒绝。
`external_approval_reference` 当前必须为 null：读取一个字符串或布尔值不能验证
外部批准。`activation_authorized` 和 `production_approved` 始终为 false。

检查财务、nonce 和配置目录互不包含，nonce 库只位于认证目录，签名配置及两个 TLS
文件只位于配置目录，wheel 位于这些可变状态/配置目录之外。财务和认证目录必须是
所声明 UID 拥有的0700目录；配置目录允许0700或0750。nonce 库和三个私有文件必须
是同 UID 的0600普通文件、单硬链接且角色 inode 不同。每个当前可见路径组件中的
符号链接均拒绝。wheel 必须是非空且非 group/other 可写的普通文件。

元数据检查前后比较 dev/inode/mode/UID/GID/link count/size/mtime/ctime，变化时
拒绝。此为两次观察，不是原子文件系统快照、文件锁、capability 或抵抗并发恶意
替换的证明。应在隔离且已停止旧写入者的准备环境运行；检查器不停止任何进程。

## 未验证的内容与发布门槛

检查器不打开 SQLite、不读 wheel、secret、profile 或规则文件内容，不验证声明中
的 artifact digest、代码真实性、SQL schema、实际 WAL/FULL 配置、TLS 有效性、
测试凭证是否残留、账户/账本状态或外部批准。输出对应 `*_verified:false`。
实际发行验证继续使用既有安装/归档校验工具，私密 profile 与 TLS 配置继续由
现有运行时检查。声明 WAL/FULL 与 replication:none 不能升级为复制确认或 HA/RPO
保证。所有 G0–G7 门槛、完整停止/恢复演练和真实责任人批准保持独立。

## 部署与回滚

此提交新增离线工具、拒绝模板及测试，不修改 systemd unit、运行时、schema 或任何
金融启用入口。无需数据迁移。部署时只把该离线检查加入人工审查流水线，并继续保留
既有发行、目录和配置校验；通过结果不得自动执行 serve/publish/activate。

回滚只从审查流水线移除这一步并保留已保存的检查结果。不得删除 nonce 库、财务
目录、审计历史或改用未支持的旧二进制。工具拒绝后修正新声明或准备环境再产生新的
结果，原失败报告不覆盖。此工具本身不提供账务、存储或服务回滚能力。
