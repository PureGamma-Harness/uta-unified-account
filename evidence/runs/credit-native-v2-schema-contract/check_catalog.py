"""Syntax/catalog check only: do not execute SQL or acquire an owner."""
import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
started, tick = datetime.now(timezone.utc).isoformat(), time.monotonic()
path = ROOT / "uta/credit_native_v2.py"
data = path.read_bytes()
ast.parse(data, filename=str(path))
from uta import credit_native_v2 as native

assert (native.FORMAT, native.STAGE) == (2, "SYNTHETIC_INTERNAL")
assert (len(native.TABLE_SQL), len(native.INDEX_SQL), len(native.TRIGGER_SQL), len(native.OBJECT_SQL)) == (6, 2, 18, 26)
positive = ("install_internal_credit_v2", "acquire_credit_v2", "operation_scope",
            "synthetic_intake_scope", "assert_operation_context")
assert not any(hasattr(native, name) for name in positive)
print(json.dumps({"kind": "syntax_and_catalog_only", "source_sha256": sha256(data).hexdigest(),
    "python": sys.version, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(),
    "elapsed_seconds": time.monotonic() - tick,
    "table_count": len(native.TABLE_SQL), "index_count": len(native.INDEX_SQL),
    "immutable_trigger_count": len(native.TRIGGER_SQL),
    "marker_is_only_compiled_text": True, "positive_apis_present": False,
    "sql_executed": False, "db_created": False, "financial_admission": False}, sort_keys=True))
