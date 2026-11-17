"""Independent pure identity probes; two expected red identities, no SQL.

This does not establish successful borrowing or mutate a database. The latest
native compatibility check imports only a separate exact Git worktree, never
an archived artifact's symbol/path/code.
"""
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from uta import credit_artifact as artifact
from uta.ledger import Ledger
from uta.market_cache import MarketDecodeCache
from uta.storage import DurableLedger


def source_hash(name):
    return hashlib.sha256((ROOT / "uta" / name).read_bytes()).hexdigest()


def failure(call):
    try:
        call()
    except Exception as exc:
        return type(exc).__name__
    return None


def main():
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    baseline = artifact.credit_code_artifact()
    original_market_source = source_hash("market_cache.py")
    market_before = failure(lambda: MarketDecodeCache(0).parse("{}"))

    def changed_decode(self, payload):
        return "SYNTHETIC_CHANGED_DECODE"

    with patch.object(MarketDecodeCache, "parse", changed_decode):
        changed = artifact.credit_code_artifact()
        print(json.dumps({"case": "missing_loaded_market_cache_method", "expected_identity_changes": True,
            "actual_identity_changes": changed != baseline,
            "source_unchanged": original_market_source == source_hash("market_cache.py"),
            "original_decode_exception": market_before,
            "changed_decode_result": MarketDecodeCache(0).parse("{}"),
            "method_in_loaded_map": "uta.market_cache.MarketDecodeCache.parse" in baseline["loaded_credit_engine"]}, sort_keys=True))

    original_ledger_source = source_hash("ledger.py")
    before_units = DurableLedger._stored_units("100")
    with patch.object(Ledger, "_LIMIT", 100):
        changed = artifact.credit_code_artifact()
        print(json.dumps({"case": "missing_ledger_class_financial_limit", "expected_identity_changes": True,
            "actual_identity_changes": changed != baseline,
            "source_unchanged": original_ledger_source == source_hash("ledger.py"),
            "original_stored_units": before_units,
            "changed_stored_units_exception": failure(lambda: DurableLedger._stored_units("100")),
            "class_limit_in_constants": "uta.ledger.Ledger._LIMIT" in baseline["loaded_credit_constants"]}, sort_keys=True))

    retained = dict(baseline)
    retained["execute"] = "arbitrary.archived.module"
    imported = []
    def no_import(name, package=None):
        imported.append(name)
        raise AssertionError("retained artifact selected import")
    with patch.object(importlib, "import_module", no_import):
        try:
            artifact.parse_credit_artifact(artifact._json(retained), expected_id="unused")
        except artifact.CreditArtifactError as exc:
            print(json.dumps({"case": "unknown_archive_data", "typed_code": exc.code,
                "imports": imported}, sort_keys=True))

    malformed = ("{", "{\"format\":1,\"format\":1}", "{\"format\":NaN}", "{\"format\":1.0}")
    typed = []
    for raw in malformed:
        try:
            artifact.parse_credit_artifact(raw, expected_id="unused")
        except artifact.CreditArtifactError as exc:
            typed.append(exc.code)
    print(json.dumps({"case": "strict_parser", "inputs": len(malformed), "typed_errors": typed}, sort_keys=True))

    compatibility = Path(sys.argv[1]).resolve()
    code = "from uta.credit_artifact import credit_code_artifact; import json; a=credit_code_artifact(); print(json.dumps({'case':'latest_native_26f_compatibility','financial_source_function_in_loaded_map':'uta.credit_native._verify_financial_source' in a['loaded_credit_engine'],'activation_permission':a['activation_permission'],'function_count':len(a['loaded_credit_engine']),'constant_count':len(a['loaded_credit_constants'])},sort_keys=True))"
    completed = subprocess.run([sys.executable, "-c", code], cwd=compatibility,
        capture_output=True, text=True, timeout=2, check=False)
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    print(json.dumps({"case": "window", "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.monotonic() - clock,
        "compatibility_exit": completed.returncode, "known_identity_red_count": 2,
        "sql_used": False, "database_created": False}, sort_keys=True))
    # Keep known identity failures red; this is not a passing acceptance test.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
