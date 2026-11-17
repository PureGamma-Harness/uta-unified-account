"""Pure AST/file/hash and bounded policy-model checks; no harness imports."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    directory = root / 'docs/reviews/auth-h0-p2p3-preparation'
    code = sorted((root / 'tests/auth_h0_p2p3_independent').glob('*.py'))
    code += sorted(directory.glob('*.py'))
    hashes, nodes = {}, {}
    for path in code:
        raw = path.read_bytes()
        nodes[path.name] = ast.parse(raw, filename=str(path), feature_version=(3, 10))
        hashes[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        assert not any(isinstance(node, ast.ImportFrom) and (node.module or '').startswith('uta')
                       for node in nodes[path.name].body)
    supervisor = nodes['detached_supervisor.py']
    bundle_node = next(node.value for node in supervisor.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'BUNDLE' for target in node.targets))
    bundle = ast.literal_eval(bundle_node)
    assert all(hashes[name] == value for name, value in bundle.items())
    assert len(bundle) == 3
    for name in ('default_handles_probe.py', 'reply_loss_probe.py', 'detached_supervisor.py'):
        assert isinstance(nodes[name].body[-1], ast.If)
        assert ast.unparse(nodes[name].body[-1].test) == "__name__ == '__main__'"
    p2 = (root / 'tests/auth_h0_p2p3_independent/default_handles_probe.py').read_text()
    p3 = (root / 'tests/auth_h0_p2p3_independent/reply_loss_probe.py').read_text()
    assert 'PLANNED_INVOCATIONS = 262' in p2 and 'range(224)' in p2 and 'range(32)' in p2
    assert 'projected > 25' in p2 and "status = 'NOT_COMPLETED'" in p2
    assert 'os._exit(73)' in p3 and "child.wait(timeout=5)" in p3
    assert 'signal.pidfd_send_signal' in p3 and "if cleanup['forced']" in p3
    assert not any(text in p2 + p3 for text in ('time.sleep(', 'killall', '__new__(', 'mock.'))
    # Independent bounded specification model, NOT an executed runtime oracle.
    occupancy_checks = 0
    for ordinary in range(225):
        for query in range(257 - ordinary):
            total = ordinary + query
            permit_normal, permit_query = total < 224, total < 256
            assert not permit_normal or total + 1 <= 224
            assert not permit_query or total + 1 <= 256
            if 224 <= total < 256:
                assert not permit_normal and permit_query
            occupancy_checks += 1
    actual_model = [224, 0]
    assert sum(actual_model) < 256 and not sum(actual_model) < 224
    actual_model[1] += 32
    assert sum(actual_model) == 256
    actual_model[0] -= 1
    assert sum(actual_model) == 255 and not sum(actual_model) < 224
    actual_model[1] -= 31
    assert sum(actual_model) == 224 and not sum(actual_model) < 224
    actual_model[1] -= 1
    assert sum(actual_model) == 223 and sum(actual_model) < 224
    actual_model[0] += 1
    assert sum(actual_model) == 224
    # Any forced cleanup in this specification is terminal UNKNOWN, even if a
    # later original-CID read could resolve an auth observation.
    cleanup_checks = 0
    for ready in (False, True):
        for go in (False, True):
            for returned in (False, True):
                for marked in (False, True):
                    for reaped73 in (False, True):
                        for queried in (False, True):
                            for forced in (False, True):
                                passed = all((ready, go, returned, marked, reaped73, queried)) and not forced
                                assert not forced or passed is False
                                assert not passed or returned and marked and reaped73
                                cleanup_checks += 1
    report = {'status': 'STATIC_PREPARATION_ONLY', 'python310_ast_files': len(code),
              'code_sha256': hashes, 'bundle_hashes_match_supervisor': True,
              'independent_policy_occupancy_states': occupancy_checks,
              'independent_replyloss_boolean_states': cleanup_checks,
              'model_results_are_not_dynamic_authdb_results': True,
              'SQL_or_DB_or_product_import_or_probe_execution': False,
              'P2_actual_status': 'NOT_RUN', 'P3_actual_status': 'NOT_RUN',
              'root_execution_GO_required': True, 'production_approved': False}
    assert not args.result.exists()
    args.result.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'code_sha256'}))


if __name__ == '__main__':
    main()
