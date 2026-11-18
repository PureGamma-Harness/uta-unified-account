# M0 一次专用分支方案 v2：不合main、仍未push或执行

原dispatch-only草案 `a28d4a636d429a510da557cdafb21ca6126c2e78` 与其35/37次纯stub结果、官方平台限制及privacy设计全部保留。原 `.github/workflows/independent-m0.yml` 不改变。这一窄补充新增 `.github/workflows/independent-m0-once.yml`，仅用于根独立审查后授权的一个新测试分支；不是任意push压测，也不是新的金融版本或909修改。

## 两个提交避免自引用

1. **C，控制版本。** 根先独立审实际controller/workflow/tests/docs和各字节SHA。C没有 `config/independent-m0-approved.json`。仅把普通规划分支推C不会触发M0。控制器默认PREP，只有具体root GO才能继续。
2. **M，唯一执行登记。** 根批准后，从exact C生成单parent提交M，唯一diff必须是新增 `config/independent-m0-approved.json`。该非秘密manifest绑定C、controller/workflow字节SHA、source909及tree、精确固定argv-spec和所有预算、one-shot registration ID、fresh workspace host/boot reference、明确的R&D evidence retention mode。它不引用自己的M SHA，避免循环。
3. 根审M具体diff/manifest/hash后，**仅一次**把M推到 `refs/heads/perf/approved-m0-20261117-once`。这是外部根操作授权来源；checksum/`execution_authorized=true`自身不是权限证明。本轮没有创建marker/M/远程分支，也没有push。

workflow只匹配这个literal分支；job另检查event=push、created=true、before=40个0、attempt1。分支更新、rerun、其它branch/event没有负载许可。登记checkout是M，controller另checkout C，workload另checkout909。bootstrap先核M的sole-parent=C且git name-status只含 `A\tconfig/independent-m0-approved.json`；controller再次核provider event/关系、manifest全部字段、canonical类型敏感argv/budget（bool不能冒充0/1）、C中实际两份代码的SHA和实际controller HEAD。被审的workflow在C..M不能改变。

只信任被授权的仓库写入者/根具体push；这不是对恶意repo管理员的密码学审批系统。不得删除后重建分支来重用registration；任何首次失败/UNKNOWN保持原run，需新方案和新root登记而非rerun-to-green。未来若需要自动跨registration全局防重，需要另一个已审持久registry，本小范围没有声称实现它。

## 不变的执行、资源和公开边界

实际链路仍是单hosted job、case B后P串行，各1driver+2真实owner/native子进程、同一个deterministic min-allowed CPU。workload exact909全5518 Git blobs/current bytes/tree核对，源前后不变；单VM实际CPU/OS/Python/SQLite/network/storage元数据记录。必须与fresh workspace boot和hostname SHA均不同；不把此扩大成物理宿主/AZ/云provider灾备证明。

独立runner门槛2,214,592,512B（2GiB额外+32MiB case+32MiB cleanup）保留，case32MiB/aggregate64MiB、50s+2s+2s、完整外层<=60s、job6分钟及所有首fail/unknown停止P不变。source/controls/receipt/reopen/classification与root prior资格来源均按原草案；profile仅诊断，不比较B/P成speedup。原workspace预算和job一字不动。

当前实现依然只有safe scalar/full-profile-semantic投影。它明确不是full原stdoutstderr，private raw只在runner生命周期存续，不能称durable retention。manifest只能声明 `safe_projection_private_ephemeral_R&D_only`；声称未实现的fullraw/encryption模式会被拒绝。root若需要完整原streams跨runner结束存续，必须先从retention-options.json选择并授权/独立验收完整递归白名单或仅encrypted stdout/stderr escrow；本版没有生成key或实现CMS加密，也不打包DB/request/keys/nonces/signatures。

## 精确但未执行的根步骤

模板位于 `docs/evidence/independent-actions-m0/once-registration-template.json`，默认 `execution_authorized=false` 且control_commit为全0，不能执行。根必须在review后另新worktree/root登记里填实际C及代码SHA、真实workspace参考；不要直接推本模板。M必须只新增marker，不添加/改任何工具、workflow、source或其它文件。执行argv的唯一动态值是已记录Python/workload checkout和新RUNNER_TEMP路径，所有业务flags与case顺序在manifest字节内固定。

```
# 仅审查说明，当前未执行、不是本提交的授权：
# git worktree add -b <new-registration-branch> <new-private-registration-worktree> <reviewed-C>
# 写入已具体批准的 config/independent-m0-approved.json（没有private keys/nonces）
# git add config/independent-m0-approved.json && git commit -m '<root-reviewed once registration>'
# 核 sole-parent、exact one-file A diff、manifest/control/source hashes，得到 M
# root给出具体GO后：git push origin <M>:refs/heads/perf/approved-m0-20261117-once
```

这一步会触发exact批准负载，故不能当一般可逆“发布草案”提前做。其它已有常规CI可能照常运行，它不等于M0被批准。若provider/job gating不同预期，则保留原结果NO_GO，不改触发来追绿。

## 本轮实际验证与回滚

新增once关系/分支/attempt/bool类型/代码diff/budget篡改等stub后，共49项纯控制测试首次通过。新增原cmd/cwd/时间/outer monotonic/hash/stdoutstderr独立保留，旧35/37原件未改。没有SQL/product/native/profile/Actions运行或任何push；只读官方API行为另有记录。stub不证明真实Actions/scheduler/owned cleanup/磁盘或隐私验收已经通过，实际仍须根与独立组review后的一次新试验。

回滚为不创建/不push专用分支；若日后已运行，停用后续入口并保留完整首结果与批准scope。源909、old24、原smoke/任何金融authority不部署、不迁移、不回滚。
