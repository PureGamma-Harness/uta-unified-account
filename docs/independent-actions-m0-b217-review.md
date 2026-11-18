# b217552 独立纯关闭：receipt组件通过，执行仍未批准

固定C：`b2175525fa90595c530999f44140e9411421528d`，controller SHA-256：`df7e8d3dfc9d22a65b197eda5cf1a0469c7e231eb1ee5ab02b03dca2869723db`。结论为 **PASS_RECEIPT_PURE_COMPONENT_ONLY**。整体仍 **NO_GO**，不授予远端M0、SQL/native、Actions、M登记、push或真实资金执行权；下一CMS提交不在本次审查内。

最小源码diff仅改变 `project_arrivals` 的receipt error检查；对比deb3，其余controller函数AST全部相同。源909 `uta/durable_commands.py:381` 的持久error确为精确 `{code,message,status}`，新检查对应其形状：REJECTED.error可为dict或strict JSON，status为exact int100..599，code/message为字符串；SUCCEEDED.error必须明确存在且None。只公开数字status，不公开原code/message。

## 原输入与参考形状的精确处理

原e444两个positive省略error，deb3新边界positive又省略message；它们保留为当时partial shape正例，不能冒称现在仍是完整source909输入。新参考夹具只补正常source字段：成功error=None；业务/控制拒绝分别为400/503，且含正常code/message。

原八个反例数值和变异含义不变。第八项金融成功→业务拒绝时补一个合法400错误，使拒绝仍来自 `cross_file_outcomes`，而非不完整error。新增四分类反例的status400/503矛盾保留正常code/message，非JSON与缺status仍各自隔离其原失败依据。所有适配逐行patch及原helper SHA保留，旧首RED和旧partial正例输出未修改。

## 实际纯复核

两次均固定CPU3，直接读取不可变Git/AST；Git元数据读取后禁止controller subprocess入口，没有导入 `uta`/`sqlite3` 或启动负载、owner、SQL、profile、Actions。没有读私钥、执行CMS或创建实际M/授权marker。

- 原八项关闭：`19:31:44.376614–19:31:44.447100 UTC`，70,488,037ns，两个完整正例接受，八反例全部以对应GateError拒绝。
- receipt及继承边界：`19:31:44.576202–19:31:44.944929 UTC`，368,747,898ns，26项控制、零RED。原四项分别以 `receipt_rejection_classification`（两项）、`rejection_error_json`、`rejection_error_shape` 拒绝。
- 正常dict/strict-JSON error均通过，status100/499业务、500/599控制边界通过；bool、float、99、600、NaN、Inf拒绝。SUCCEEDED.error为非None拒绝。公开投影不包含合成code/message内容。
- 原bounded-gzip、不先全量解压、解码前单行上限、逐步8MiB限制，以及56+2+2 fake-owner包围hash/parser/fsync、UNKNOWN保留首字节、61秒收集quarantine控制仍通过。这些是纯桩，不证明真实OS清理或硬实时。

两组原stdout/stderr、adapter patch、源码/测试/作者83项证据的输入摘要见 `review-manifest.json`。共36项纯控制均按预期，无新RED；没有通过重跑覆盖任何失败。作者83项通过未作为这次独立结果的替代，也没有重新运行实际工作负载。

## 余下门槛与回滚

本次关闭仅限receipt/parser组件和继承的纯控制范围。root已要求实际远端首次执行前完成独立的CMS AuthEnvelopedData AES256GCM stdout/stderr-only escrow实现及fixture审查。本次没有评估尚未提交的crypto代码，不能将private-ephemeral模式当完整raw持久交付；物理watchdog/清理、远端硬件、容量、HA与生产资格仍未验证。

本提交只新增独立审查脚本、合成证据和说明，无运行时/API/数据库/部署变更。回滚可撤销该review提交；原e444/deb3/b217、所有首RED和原实验必须保留，source909和原authority均未改变。
