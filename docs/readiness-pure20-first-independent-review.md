# 首 pure20：独立原件核对，保留 RED

固定首封存 `9648476962427504cc790c3728b32c2a5757e96d`，target source `59efb56f86de49c51bbea7407c3be447332df216`、plan2bda673、物化记录6c361072。**FIRST_PURE20_RED_RAW_BINDING_CONFIRMED。** 独立审查没有执行新旧fixture、目标模块、native、SQL、PID/pidfd、child、信号或网络。

完整首stdout明确20方法：guard9方法和terminal10方法逐项ok，另一个sticky/inflight方法的3个subtest ERROR；0 FAIL、0 skipped、exit1。不能记成17 PASS，也不能把三ERROR当三个独立失败方法。三项均在SimpleNamespace被用于bindings dict key处抛TypeError，随后postbinding guard assertions没有执行；该记录不证明生产guard失败或修复通过。

stdout8,678B/SHA `9e045d03be1fed1c7e35378f0882bfc8d95102dd67c2b97a990b8fdad6e191ed`、stderr0B、实际exit文件1均与result匹配；自然产生的原始尾空格保留，未清理原件。BEGIN/END完整，unittest8.384s、runner8.519232224993175s、actual affinity[0]、forbidden imports空。实际CPU ID0没有改称CPU ID1。

独立核target4+fixture/runner4共8项源码length/SHA：plan、source Git、首封存tip、raw前后pins及result一致。AST只读计数对应GuardFocusedCases9与TerminalFocusedCases11，未调用这些定义。

物化记录SHA `f9372859cfc524e57c3bfc44ed34681603145a6d9f8afd80dce22a64ce1cc8ed`匹配intent。78项逐条核approved Git blob、length、file/blob SHA、捕获stat.size及posthash；21旧SAFE逐条核before/after、原Git、首封存Git及posthash。全部一致。这验证既有源码与物化证据的绑定，没有重做当前物理物化，也不是native能力证明。

原pure7一次PASS、guard首1 PASS/5 RED、terminal首1 PASS/7 RED及两项原CI FAIL均保持各自结论。新批次没有运行这些旧fixture executable。修正单一Process stand-in必须用新的source/driver/plan及独立一次预算，不能把首pure20改成PASS或重跑其余19方法；identity hash应保留原生Process的对象身份相等语义。

完整逐项绑定见 [独立记录](../evidence/reviews/readiness-pure20-first-independent/raw-source-and-materialization-binding.json)。本OWN只新增独立文档和绑定记录，不改作者原件、源码、规则、schema或服务。回滚移除本OWN新增文件并保留全部首RED；preflight/native、金融、容量与生产批准仍为false。
