"""Pure AST and manual arithmetic check; never import/run the ABBA harness.

Only the two small arithmetic functions are compiled from their isolated ASTs.
No UTA import, SQLite, service, process spawn, fixture or profile can run here.
This is author preparation, not independent review or dynamic finance evidence.
"""
import ast
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PATH = HERE / "run_uninstrumented_abba.py"
data = PATH.read_bytes()
tree = ast.parse(data, filename=str(PATH))
checks = []


def require(condition, name):
    assert condition, name
    checks.append(name)


assignments = {node.targets[0].id:node.value for node in tree.body
               if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
require(ast.literal_eval(assignments["SCALES"]) == (512,4096), "fixed scale order 512 then 4096")
require(ast.literal_eval(assignments["ORDER"]) == (False,True,True,False), "ABBA uses complete default and opt-in proofs")
require(ast.literal_eval(assignments["BLOCKS"]) == 3, "three four-call blocks per scale gives 24 proofs")
imports = [alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names]
require(not any(name in imports for name in ("cProfile","profile","pstats","tracemalloc")), "no profiler or memory tracer imported")
require(not any(isinstance(node,ast.Attribute) and node.attr in
    {"set_trace_callback","setprofile","settrace","row_factory"} for node in ast.walk(tree)), "no trace installation or custom row factory")
slot_loop = next(node for node in ast.walk(tree) if isinstance(node,ast.For)
    and isinstance(node.target,ast.Tuple) and [n.id for n in node.target.elts] == ["slot","mode"])
body = [ast.unparse(node) for node in slot_loop.body]
first = body.index("wall_start = time.monotonic_ns()")
last = body.index("wall_end = time.monotonic_ns()")
require(body[first:last+1] == ["wall_start = time.monotonic_ns()",
    "cpu_start = time.process_time_ns()", "returned = ledger.verify(ordered_postings=mode)",
    "cpu_end = time.process_time_ns()", "wall_end = time.monotonic_ns()"],
    "timed region contains only clocks and complete ordinary verifier call")
require("assert returned == count" in body[last+1:], "count checked after clocks stop")
require(any("timed_verify.begin" in text for text in body[:first]), "failed timed calls retain explicit identity before clock starts")
require(any("samples_file.write" in text for text in body[last+1:]), "raw sample serialization is after clocks stop")
require(any(isinstance(node,ast.Assert) and ast.unparse(node.test) == "type(database) is Database"
            for node in ast.walk(tree)), "measurement authorities require ordinary Database")

arithmetic = [node for node in tree.body if isinstance(node,ast.FunctionDef)
              and node.name in {"fraction_record","block_report"}]
require(len(arithmetic) == 2, "only two isolated arithmetic functions selected")
namespace = {"Fraction":Fraction,"ORDER":(False,True,True,False)}
exec(compile(ast.Module(body=arithmetic,type_ignores=[]),"isolated_abba_arithmetic","exec"),namespace)
samples = [dict(ordered_postings=mode,wall_ns=w,cpu_ns=c)
           for mode,w,c in zip((False,True,True,False),(10,12,14,12),(4,6,8,6))]
result = namespace["block_report"](samples)
literal = {
    "wall_ns":{"a_mean":{"numerator":11,"denominator":1},"b_mean":{"numerator":13,"denominator":1},
        "b_over_a":{"numerator":13,"denominator":11},"b_minus_a_mean":{"numerator":2,"denominator":1}},
    "cpu_ns":{"a_mean":{"numerator":5,"denominator":1},"b_mean":{"numerator":7,"denominator":1},
        "b_over_a":{"numerator":7,"denominator":5},"b_minus_a_mean":{"numerator":2,"denominator":1}}}
require(result == literal, "manual ABBA means, denominator direction and slower signed delta exact")
try:
    namespace["block_report"](samples[::-1])  # ABBA is symmetric; deliberately change one mode below instead.
    invalid = [dict(sample) for sample in samples]
    invalid[1]["ordered_postings"] = False
    namespace["block_report"](invalid)
except AssertionError:
    checks.append("malformed order rejected")
else:
    raise AssertionError("malformed order accepted")
ratios = [Fraction(13,11),Fraction(9,10),Fraction(1,1)]
require(sorted(ratios)[1] == Fraction(1,1), "manual three-block median preserves mixed slower/faster outcomes")
print(json.dumps(dict(status="AUTHOR_AST_ARITHMETIC_ONLY_NOT_RUN",
    harness_sha256=sha256(data).hexdigest(),checks=checks,check_count=len(checks),
    sql_tests_profiles_executed=False,independent_acceptance=False),indent=2,sort_keys=True))
