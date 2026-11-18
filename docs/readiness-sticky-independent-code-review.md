# Isolated sticky方法：独立 CODE 闭合

固定提案 `705244611e1f33fdb8e4f8e520c109edd7d4b630`、fixture修订cb76afd、driver19eebff；native target仍为 `59efb56f86de49c51bbea7407c3be447332df216`。**原SimpleNamespace的Process协议finding按CODE关闭；新方法尚未执行。**

局部ProcessStandin只有pid/name与普通构造函数，没有自定义eq/hash或slots，保留object identity相等/哈希及weakref能力；可变pid/name不参与相等性。它不是给SimpleNamespace只补hash的值相等别名。将新方法的三个stand-in调用静态还原成旧SimpleNamespace、移除局部class后，整方法AST与首source完全相同；原断言、mutation及异常预期均未改。

四个native文件在target59ef与提案tip逐字节不变。新driver只构造这一个明确TestCase：initial sticky denial加原三个ERROR子例，共四轨迹，不选择另19方法、whole20或原7/guard6/terminal8 executable。此方法所用case_namespace只依赖选出的common/case AST；两个target与三个fixture/driver共五项length/SHA均匹配plan及Git。plan SHA为 `1b3767d1b247aa61a7efb764f7c96196f94136876f94170bba3ee3971b4a4888`。

10s trace、一个实际允许CPU并记录其ID、共用256KiB RawStream及512B trailer reserve、native effect audit和forbidden imports检查保持。纯范围只有内存/惰性spy与所选AST；没有native、SQL、proc/pidfd、child、signal或network权限。新文件的正规物化还应由独立既定记录绑定；此CODE审查没有重做物化或执行任一方法。

原pure20的六个首文件逐字节保留，仍为19明确OK、1方法3 ERROR、exit1；postbinding断言不能因本CODE修复被追认为已通过。未来isolated结果须有新source/intent/原始输出与具体一次预算；不能重写原首RED，也不授权preflight/native。

静态还原与五项绑定见 [独立记录](../evidence/reviews/readiness-sticky-code/static-code-and-five-pins.json)。本OWN只新增独立文档与记录，无目标、规则、schema或服务修改；回滚移除本OWN新增材料并保留全部首证据。生产和真实资金批准仍为false。
