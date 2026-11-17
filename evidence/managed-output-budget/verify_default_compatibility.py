"""Read-only AST/byte comparison to the immutable pre-budget candidate."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = '8b7f544fcbdfd540d43de1d6560022c6ebbd3799'


def original(name):
    return subprocess.check_output(['git', '--no-optional-locks', 'show', f'{BASE}:{name}'], cwd=ROOT)


def functions(raw):
    return {item.name: item for item in ast.parse(raw).body
            if isinstance(item, (ast.FunctionDef, ast.ClassDef))}


def dump(node):
    return ast.dump(node, include_attributes=False)


class UnwrapOutputWrites(ast.NodeTransformer):
    def visit_Call(self, node):
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'write_output':
            node.func, node.args = node.args[0], node.args[1:]
        return node


def main():
    protected = {
        'tools/run_managed_long.py': ['producer_command', 'observer_command',
            'financial_drain_before_log', 'Pipes', 'Timeline', 'final_once', 'request_observer_stop'],
        'tools/prepare_managed_stability.py': ['commands', 'authorized', 'cohost_budget',
            '_pidfd_term', '_original_smoke_drain'],
    }
    checks = {}
    for name, names in protected.items():
        old, new = functions(original(name)), functions((ROOT / name).read_bytes())
        checks[name] = {key: dump(old[key]) == dump(new[key]) for key in names}
        assert all(checks[name].values())
    name = 'tools/run_managed_long.py'
    old, new = functions(original(name))['supervise'], functions((ROOT / name).read_bytes())['supervise']
    old_collect = next(item for item in old.body if isinstance(item, ast.FunctionDef) and item.name == 'collect')
    new_collect = next(item for item in new.body if isinstance(item, ast.FunctionDef) and item.name == 'collect')
    old_legacy = old_collect.body[-1].body[2:]
    new_legacy = new_collect.body[-1].body[-1].body
    same_legacy = dump(ast.Module(body=old_legacy, type_ignores=[])) == dump(
        UnwrapOutputWrites().visit(ast.Module(body=new_legacy, type_ignores=[])))
    assert same_legacy
    def final_gate(node):
        return next(item for item in ast.walk(node) if isinstance(item, ast.Call)
                    and any(isinstance(part, ast.Constant) and part.value == 'final-summary.json'
                            for part in ast.walk(item)))
    same_final_gate = dump(final_gate(old)) == dump(UnwrapOutputWrites().visit(final_gate(new)))
    assert same_final_gate
    unchanged = ['tools/managed_observer_coverage.py', 'tools/managed_soak_observer.py',
                 'tools/managed_observer_smoke.py', 'benchmarks/run_managed_soak.py']
    listed = subprocess.check_output(['git', '--no-optional-locks', 'ls-tree', '-r', '--name-only', BASE,
        'uta', 'benchmarks/plans', 'benchmarks/profiles'], cwd=ROOT, text=True).splitlines()
    unchanged.extend(listed)
    hashes = {}
    for name in unchanged:
        raw = original(name)
        assert (ROOT / name).read_bytes() == raw, name
        hashes[name] = sha256(raw).hexdigest()
    old_constant = next(item for item in ast.parse(original('tools/run_managed_long.py')).body
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'OUTPUT_CAP' for target in item.targets))
    new_constant = next(item for item in ast.parse((ROOT/'tools/run_managed_long.py').read_bytes()).body
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'OUTPUT_CAP' for target in item.targets))
    assert dump(old_constant) == dump(new_constant)
    print(json.dumps(dict(base=BASE, protected_function_ast_equal=checks,
        legacy_three_file_measurement_ast_equal_after_transparent_write_wrapper=same_legacy,
        final_summary_financial_coverage_clock_gate_ast_equal_after_transparent_write_wrapper=same_final_gate,
        output_cap_assignment_ast_equal=True, unchanged_file_sha256=hashes,
        no_qualification_or_execution_claim=True), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
