"""Execute only the original peer's pure R5 block; never its dummy/main."""
import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import time
source=Path(__file__).with_name('run-review.py')
spec=importlib.util.spec_from_file_location('original_peer_pure_output_control',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
parsed=ast.parse(source.read_text());main=next(node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name=='main')
blocks=[node for node in main.body if isinstance(node,ast.With) and any(
 isinstance(item.context_expr,ast.Call) and any(key.arg=='prefix' and isinstance(key.value,ast.Constant)
 and key.value.value=='uta-independent-runner-report-' for key in item.context_expr.keywords) for item in node.items)]
assert len(blocks)==1
namespace=vars(module);namespace['records']={};at=time.monotonic()
exec(compile(ast.Module(body=blocks,type_ignores=[]),str(source)+'#pure-report-block','exec'),namespace)
record={'original_script_sha256':sha256(source.read_bytes()).hexdigest(),'selected_original_AST_lines':[blocks[0].lineno,blocks[0].end_lineno],
 'original_main_and_dummy_executed':False,'collector_verifier_SQL_service_or_benchmark_executed':False,
 'outcome':namespace['records']['report_output_path_control'],'seconds':time.monotonic()-at,'production_approved':False}
assert record['outcome']['outcome']['accepted'] is False
Path(__file__).with_name('original-pure-output-result.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,sort_keys=True))
