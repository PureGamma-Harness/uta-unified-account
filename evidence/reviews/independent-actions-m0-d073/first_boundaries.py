"""Independent tiny-file checks; no SQL, native workload, crypto or Actions."""
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tools/independent_m0_controller.py"
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == "57fc60bc914264d1fbd4d0b5c907222f3743ebbbbb332af30f8d043cec90302c"
spec = importlib.util.spec_from_file_location("independent_m0_d073", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def scenario(name, location, expected_reject):
    with tempfile.TemporaryDirectory(prefix="m0-d073-independent-") as temporary:
        root = Path(temporary)
        private, public = root / "private", root / "public"
        private.mkdir(mode=0o700)
        public.mkdir(mode=0o700)
        (private / "B").mkdir(mode=0o700)
        parent = {"valid_private": private / "B/workload/authority",
                  "public_safe_tree": public / "case-B-safe/B/workload/authority",
                  "wrong_nested_case": private / "B/P/workload/authority"}[location]
        parent.mkdir(parents=True)
        main = parent / "shard-0000.sqlite3"
        aux = parent / "shard-0000.sqlite3-shm"
        main.write_bytes(b"m")
        aux.write_bytes(b"x")
        original = Path.lstat
        calls = []

        def vanished(path, *args, **kwargs):
            if path == aux and not calls:
                calls.append(True)
                path.unlink()
                raise FileNotFoundError(errno.ENOENT, "owned synthetic disappearing file", str(path))
            return original(path, *args, **kwargs)

        rejected = False
        error = None
        measured = None
        try:
            with patch.object(Path, "lstat", vanished):
                measured = m.case_bytes(private, public, "B")
        except (m.GateError, FileNotFoundError) as failure:
            rejected = True
            error = type(failure).__name__ + ":" + str(failure).split(temporary)[0]
        passed = rejected == expected_reject and (expected_reject or measured == 1)
        return {"name": name, "status": "PASS" if passed else "RED",
                "expected_reject": expected_reject, "actually_rejected": rejected,
                "measured_bytes": measured, "error": error,
                "target_stat_disappearance_count": len(calls),
                "location_without_private_prefix": location}


if __name__ == "__main__":
    cases = [scenario("valid_private_known_case_aux_recovers", "valid_private", False),
             scenario("public_safe_tree_must_not_borrow_private_aux_exemption", "public_safe_tree", True),
             scenario("nested_wrong_case_must_not_borrow_known_layout", "wrong_nested_case", True)]
    print(json.dumps({"candidate": "d07302252736ab7cb8a9338078b913ef33e728c0", "cases": cases,
                      "sql_native_crypto_actions_workload_executions": 0}, sort_keys=True))
    raise SystemExit(1 if any(c["status"] == "RED" for c in cases) else 0)
