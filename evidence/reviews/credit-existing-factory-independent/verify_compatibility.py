"""Independent, pure exact-AST compatibility comparison; requires Git history."""
import ast
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = "143fe601f2058b87f9a9dfb431954c2efc174e0f"


def original(file):
    return subprocess.check_output(["git", "show", BASE+":"+file], cwd=ROOT, text=True)


def function(source, cls, name):
    module = ast.parse(source)
    owner = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == cls)
    return next(node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == name)


def dump(node):
    return ast.dump(node, include_attributes=False)


def compare():
    results = {}
    for file, cls in (("uta/storage.py", "DurableLedger"), ("uta/service.py", "ExchangeService"),
                      ("uta/credit.py", "CreditService")):
        before = function(original(file), cls, "__init__")
        after = function((ROOT/file).read_text(), cls, "__init__")
        index = next(i for i, arg in enumerate(after.args.kwonlyargs) if arg.arg == "_existing_connection")
        after.args.kwonlyargs.pop(index)
        after.args.kw_defaults.pop(index)
        removed, body = [], []
        for node in after.body:
            if (isinstance(node, ast.If) and any(isinstance(value, ast.Name) and value.id == "_existing_connection"
                                                for value in ast.walk(node.test))):
                removed.append(ast.unparse(node.test))
            else:
                body.append(node)
        after.body = body
        results[cls+".default_constructor"] = {
            "equivalent_after_removing_only_new_parameter_and_existing_branches": dump(after) == dump(before),
            "removed_conditions": removed}
    before, after = original("uta/credit.py"), (ROOT/"uta/credit.py").read_text()
    for name in ("_repay", "repay", "_record", "_prepare"):
        results["CreditService."+name] = {
            "ast_unchanged": dump(function(before, "CreditService", name)) == dump(function(after, "CreditService", name))}

    def tail(source, remove_audit):
        body = next(node for node in function(source, "CreditService", "_borrow").body if isinstance(node, ast.With)).body
        start = next(i for i, node in enumerate(body) if isinstance(node, ast.Expr)
                     and ast.unparse(node.value).startswith("self.exchange._require_exposure_allowed("))
        selected = body[start:]
        if remove_audit:
            selected = [node for node in selected if not (isinstance(node, ast.If) and ast.unparse(node.test) == "audit is not None")]
        return [dump(node) for node in selected]

    results["CreditService._borrow.financial_tail"] = {
        "unchanged_except_dedicated_audit_completion": tail(before, False) == tail(after, True)}
    return results


if __name__ == "__main__":
    results = compare()
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(all(value for key, value in row.items() if key != "removed_conditions")
                             for row in results.values()) else 1)
