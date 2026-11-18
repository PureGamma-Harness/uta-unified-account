"""Pure four-stream/publication/budget review; all crypto/processes stubbed."""
import ast
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

C = "5d4b5c7cb02ff3c365532e16faead233093faac9"
REPO = Path(__file__).resolve().parents[3]


def main():
    began = time.monotonic_ns(); started = datetime.now(timezone.utc).isoformat()
    inputs = {name: subprocess.check_output(["git", "show", C + ":" + name], cwd=REPO) for name in
              ["tools/m0_stream_escrow.py", "tools/independent_m0_controller.py", "tests/test_independent_m0_escrow.py"]}
    e, c = ModuleType("fixed_escrow_pure_flow"), ModuleType("fixed_control_pure_flow")
    e.__file__ = "/synthetic/control/tools/m0_stream_escrow.py"
    c.__file__ = "/synthetic/control/tools/independent_m0_controller.py"
    forbidden = []; observations = []

    def prohibited(*args, **kwargs):
        forbidden.append("process-entry")
        raise AssertionError("real OpenSSL/native/workload forbidden in pure flow")

    with patch.object(subprocess, "Popen", prohibited), patch.object(subprocess, "run", prohibited), \
            patch.object(subprocess, "check_output", prohibited), patch.object(subprocess, "call", prohibited):
        exec(compile(inputs["tools/m0_stream_escrow.py"], e.__file__, "exec"), e.__dict__)
        exec(compile(inputs["tools/independent_m0_controller.py"], c.__file__, "exec"), c.__dict__)
        tree = ast.parse(inputs["tests/test_independent_m0_escrow.py"])
        shape = next(n for cls in tree.body if isinstance(cls, ast.ClassDef) for n in cls.body
                     if isinstance(n, ast.FunctionDef) and n.name == "helper_fixture")
        namespace = dict(e=e, c=c, os=os, Path=Path, json=json, patch=patch, redirect_stdout=redirect_stdout, io=io)
        exec(compile(ast.Module(body=[shape], type_ignores=[]), "immutable-shape-helper-only", "exec"), namespace)
        prefix = deepcopy(shape); prefix.name = "prefix_fixture"
        altered = 0
        for node in ast.walk(prefix):
            if isinstance(node, ast.DictComp) and isinstance(node.key, ast.Name) and node.key.id == "name":
                node.value = ast.Compare(left=ast.Name(id="name", ctx=ast.Load()), ops=[ast.NotEq()], comparators=[ast.Constant("case-owner.stdout")]); altered += 1
        assert altered == 1
        exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix], type_ignores=[])), "pure-prefix-input-adapter", "exec"), namespace)
        with TemporaryDirectory(prefix="m0-independent-pure-flow-") as directory:
            base = Path(directory)
            for label, failed, is_prefix in [("all_four", None, False),
                                             ("failure_first", "driver.stdout", False),
                                             ("failure_middle", "case-owner.stdout", False),
                                             ("failure_last", "case-owner.stderr", False),
                                             ("captured_prefix", None, True)]:
                root = base / label; root.mkdir()
                published = []; real_rename = os.rename

                def rename(source, target):
                    journal = json.loads((root / "private/escrow-completed-B.json").read_bytes())
                    assert journal["status"] == "IN_PROGRESS"
                    assert journal["files"][-1]["name"] == Path(target).name
                    assert sha256(Path(source).read_bytes()).hexdigest() == journal["files"][-1]["sha256"]
                    published.append(Path(target).name)
                    return real_rename(source, target)

                with patch.object(e.os, "rename", rename):
                    function = namespace["prefix_fixture" if is_prefix else "helper_fixture"]
                    code, private, public, result = function(SimpleNamespace(root=root), failed)
                expected = "PASS" if failed is None and not is_prefix else "UNKNOWN"
                assert result["status"] == expected and code == int(expected != "PASS")
                assert len(published) == (3 if failed else 4)
                assert set(published) == {s + ".cms" for s in e.STREAMS if s != failed}
                assert not result["origin_authenticated_by_recipient_encryption"] and not result["all_transitive_native_streams_claimed"]
                if failed:
                    original = private / "B" / failed if failed.startswith("driver.") else private / ("case-owner-B." + failed.split(".")[-1])
                    assert original.is_file()
                if is_prefix: assert any(f["code"] == "captured_prefix_only" for f in result["failures"])
                c.resource_usage(private, public)
                observations.append(dict(case=label, expected=expected, observed=result["status"], journal_precedes_each_atomic_publish=True,
                                         complete_ciphers_preserved=len(published), real_crypto_performed=False, red=False))
            assert c.MIN_FREE == 2348810240 and c.LEGACY_MIN_FREE == 2214592512
            assert c.AGGREGATE_CAP == 64 * 1024**2 and c.ESCROW_CAP == 96 * 1024**2
            assert c.CLEANUP_RESERVE == 32 * 1024**2 and c.TOTAL_CAP == 192 * 1024**2
            private, public = base / "budget-private", base / "budget-public"
            private.mkdir(); public.mkdir(); (public / "escrow-B-safe").mkdir()
            paths = {"normal": private / "normal-synthetic.txt", "escrow": public / "escrow-B-safe/driver.stdout.cms", "cleanup": private / "escrow-context-B.json"}
            for path in paths.values(): path.write_bytes(b"SYNTHETIC-NOT-A-DATABASE")
            exact = dict(normal=c.AGGREGATE_CAP, escrow=c.ESCROW_CAP, cleanup=c.CLEANUP_RESERVE)
            actual_lstat = Path.lstat

            def measured(over=None):
                def stat(path):
                    original = actual_lstat(path)
                    for bucket, chosen in paths.items():
                        if path == chosen:
                            return SimpleNamespace(st_mode=original.st_mode, st_size=exact[bucket] + int(bucket == over))
                    return original
                with patch.object(Path, "lstat", stat): return c.resource_usage(private, public)

            assert measured() == dict(exact, total=c.TOTAL_CAP)
            for bucket in exact:
                try: measured(bucket); raise AssertionError("over-budget accepted")
                except c.GateError as error: assert str(error) == "resource_compartment_cap"
            observations.append(dict(case="all_three_compartments_exact_and_plus_one", observed="PASS", red=False,
                                     disk_bytes_allocated_for_large_boundaries=False, exact_total=c.TOTAL_CAP, minimum_fresh_free=c.MIN_FREE))
            result = c.escrow_closed_case(SimpleNamespace(), Path("/synthetic"), base, base, "B", {}, dict(control_commit=C), [3], lambda: None)
            assert result["status"] == "UNKNOWN" and result["error_code"] == "closed_case_producers_unproven"
            observations.append(dict(case="missing_close_proof_rejected_before_crypto_owner", observed="UNKNOWN", red=False))
        assert not forbidden
        assert not any(name == "uta" or name.startswith("uta.") or name == "sqlite3" for name in sys.modules)
    print(json.dumps(dict(control_commit=C, started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          elapsed_monotonic_ns=time.monotonic_ns() - began, input_sha256={k: sha256(v).hexdigest() for k, v in inputs.items()},
                          cases=observations, red_count=0, controller_process_entry_calls=forbidden,
                          actual_OpenSSL_SQL_native_M0_Actions_private_key_read=False, execution_authorized=False, production_approved=False), indent=2))


if __name__ == "__main__": main()
