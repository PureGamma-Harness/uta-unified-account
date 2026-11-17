"""Pure temporary fdinfo fixtures for the exact AST helper; no live proc/SQL.

Expected outcomes are literal reviewer vectors. A synthetic identity provider
and path mapping are explicit controls, never evidence of a native holder.
"""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tests/test_durable_faults.py"
source = SOURCE.read_text()
node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "bound_router_shared_flocks")
function_tree = ast.Module(body=[node], type_ignores=[])
function_hash = sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
pid = 4242
identity = {"pid": pid, "start_ticks": "100", "boot_id": "synthetic-boot", "uid": os.getuid()}
os.sched_setaffinity(0, {3})
signal.alarm(2)
started = monotonic()
results = []
old_module = sys.modules.get("uta.durable_process")
old_uta = sys.modules.get("uta")
try:
    with TemporaryDirectory() as directory:
        base = Path(directory)
        target = base / "router.lock"; target.touch()
        fdinfo = base / "fdinfo"; fdinfo.mkdir()
        fds = base / "fd"; fds.mkdir()
        (fds/"7").symlink_to(target)
        info = target.stat()
        dev = f"{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}"
        otherdev = f"{os.major(info.st_dev)+1:02x}:{os.minor(info.st_dev):02x}:{info.st_ino}"
        good = f"lock: 1: FLOCK ADVISORY READ {pid} {dev} 0 EOF"
        vectors = [
            ("exact-full-file-read", good, 1),
            ("tabs-and-newline", good.replace(" ", "\t") + "\n", 1),
            ("different-owner", good.replace(str(pid), "4243", 1), 0),
            ("write-lock", good.replace(" READ ", " WRITE "), 0),
            ("posix-lock", good.replace(" FLOCK ", " POSIX "), 0),
            ("blocked-lock-record", good.replace("1: FLOCK", "1: -> FLOCK"), 0),
            ("partial-start", good.replace(" 0 EOF", " 1 EOF"), 0),
            ("finite-end", good.replace(" 0 EOF", " 0 100"), 0),
            ("extra-token", good + " extra", 0),
            ("wrong-device", good.replace(dev, otherdev), "AssertionError"),
            ("wrong-inode", good.replace(dev, dev.rsplit(":", 1)[0] + ":" + str(info.st_ino+1)), "AssertionError"),
            ("invalid-inode", good.replace(dev, dev.rsplit(":", 1)[0] + ":x"), "ValueError"),
        ]
        synthetic = ModuleType("uta.durable_process")
        synthetic._process_identity = lambda selected: dict(identity)
        sys.modules["uta"] = ModuleType("uta")
        sys.modules["uta.durable_process"] = synthetic
        def mapped_path(value):
            path = Path(value)
            prefix = f"/proc/{pid}/"
            if str(path).startswith(prefix):
                return base / str(path)[len(prefix):]
            return path
        namespace = {"Path": mapped_path, "os": os}
        exec(compile(function_tree, str(SOURCE), "exec"), namespace)
        function = namespace["bound_router_shared_flocks"]
        for label, content, expected in vectors:
            (fdinfo/"7").write_text(content)
            try:
                actual = len(function(pid, identity, target, (info.st_dev, info.st_ino)))
            except Exception as error:
                actual = type(error).__name__
            assert actual == expected, (label, expected, actual)
            results.append({"label": label, "expected": expected, "actual": actual})
        (fdinfo/"7").write_text(good)
        calls = []
        def changed(selected):
            calls.append(selected)
            return dict(identity, start_ticks="101" if len(calls)>1 else "100")
        synthetic._process_identity = changed
        try:
            function(pid, identity, target, (info.st_dev, info.st_ino))
            raise AssertionError("changed synthetic birth accepted")
        except AssertionError as error:
            assert "birth identity changed" in str(error)
        results.append({"label": "changed-birth-at-postcheck", "expected": "AssertionError", "actual": "AssertionError"})
finally:
    if old_module is None: sys.modules.pop("uta.durable_process", None)
    else: sys.modules["uta.durable_process"] = old_module
    if old_uta is None: sys.modules.pop("uta", None)
    else: sys.modules["uta"] = old_uta
signal.alarm(0)
value = {"source_commit": "3af589415ccfdb65ed84a952184a77030319a3df", "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
    "helper_AST_sha256": function_hash, "passed": True, "vectors": results,
    "wall_seconds": monotonic()-started, "cpu_ids": sorted(os.sched_getaffinity(0)),
    "scope": "temporary fdinfo text + synthetic identity only; no live proc/SQL/service/native case",
    "native_holder_proven": False, "production_approved": False}
Path(__file__).with_name("result.json").write_text(json.dumps(value, indent=2)+"\n")
print(json.dumps({k:value[k] for k in ("passed", "wall_seconds", "scope")},indent=2))
