"""Recheck the original identity counterexample inputs, without SQL or replay."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from uta import credit, credit_artifact as artifact, writer_fence
from uta.ledger import Ledger
from uta.market_cache import MarketDecodeCache
from uta.portfolio import LoanAccount
from uta.storage import DurableLedger


def failure(call):
    try:
        call()
    except Exception as exc:
        return type(exc).__name__
    return None


def source_hash(name):
    return sha256((ROOT / "uta" / name).read_bytes()).hexdigest()


def identity(manifest):
    return artifact.credit_artifact_id(manifest)


def different(case, before, after, **facts):
    result = {"case": case, "before_id": identity(before), "after_id": identity(after),
              "source_digest_equal": before["source_digest"] == after["source_digest"], **facts}
    result["actual_identity_changes"] = result["before_id"] != result["after_id"]
    print(json.dumps(result, sort_keys=True))
    assert result["source_digest_equal"] and result["actual_identity_changes"], case


# Same capture structure and values as original 1950f60 repr-probe.py.
def make(value):
    repr_running = {value}
    def user_function():
        return 0
    def __repr__(*args, **kwargs):
        return next(iter(repr_running)) + user_function()
    return __repr__


def main():
    started, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    baseline = artifact.credit_code_artifact()
    market_source = source_hash("market_cache.py")
    market_before = failure(lambda: MarketDecodeCache(0).parse("{}"))
    def changed_decode(self, payload):
        return "SYNTHETIC_CHANGED_DECODE"
    with patch.object(MarketDecodeCache, "parse", changed_decode):
        changed = artifact.credit_code_artifact()
        different("CA01_original_market_input", baseline, changed,
            source_unchanged=market_source == source_hash("market_cache.py"),
            original_decode_exception=market_before,
            changed_decode_result=MarketDecodeCache(0).parse("{}"),
            method_in_loaded_map="uta.market_cache.MarketDecodeCache.parse" in baseline["loaded_credit_engine"])

    ledger_source = source_hash("ledger.py")
    original_units = DurableLedger._stored_units("100")
    with patch.object(Ledger, "_LIMIT", 100):
        changed = artifact.credit_code_artifact()
        different("CA02_original_limit_input", baseline, changed,
            source_unchanged=ledger_source == source_hash("ledger.py"),
            original_stored_units=original_units,
            changed_stored_units_exception=failure(lambda: DurableLedger._stored_units("100")),
            class_limit_in_constants="uta.ledger.Ledger._LIMIT" in baseline["loaded_credit_constants"])

    first, second = make(101), make(202)
    with patch.object(credit.CreditService, "_borrow", first):
        before = artifact.credit_code_artifact()
    with patch.object(credit.CreditService, "_borrow", second):
        after = artifact.credit_code_artifact()
    different("CA03_original_nonstdlib_closure", before, after,
        first_result=first(), second_result=second(), same_code=first.__code__ == second.__code__,
        freevars=first.__code__.co_freevars)

    # Real stdlib wrapper, but placed at a financial method collection path.
    wrapper = LoanAccount.__repr__
    assert wrapper.__code__ is artifact._DATACLASS_REPR_CODE
    cells = dict(zip(wrapper.__code__.co_freevars, wrapper.__closure__))
    memo = cells["repr_running"].cell_contents
    marker_a, marker_b = (101, -101), (202, -202)
    assert marker_a not in memo and marker_b not in memo
    with patch.object(credit.CreditService, "_borrow", wrapper):
        try:
            memo.add(marker_a)
            before = artifact.credit_code_artifact()
            memo.remove(marker_a)
            memo.add(marker_b)
            after = artifact.credit_code_artifact()
            different("real_stdlib_wrapper_at_borrow", before, after,
                standard_wrapper_code=True,
                allowed_financial_memo_exclusion=artifact._allows_repr_memo(credit, "CreditService._borrow", wrapper))
        finally:
            memo.discard(marker_a)
            memo.discard(marker_b)

    before = artifact.credit_code_artifact()
    try:
        memo.add(marker_a)
        after = artifact.credit_code_artifact()
        print(json.dumps({"case": "actual_dataclass_repr_binding", "before_id": identity(before),
            "after_id": identity(after), "identity_unchanged": before == after,
            "standard_wrapper_code": wrapper.__code__ is artifact._DATACLASS_REPR_CODE}, sort_keys=True))
        assert before == after
    finally:
        memo.discard(marker_a)

    with patch.object(writer_fence, "_REGISTRY", {1: {"nonce": "DO_NOT_ARCHIVE_LIVE_NONCE"}}):
        unchanged = artifact.credit_code_artifact()
    assert unchanged == baseline and "DO_NOT_ARCHIVE_LIVE_NONCE" not in artifact._json(unchanged)
    print(json.dumps({"case": "live_nonce_exclusion", "identity_unchanged": unchanged == baseline,
        "nonce_archived": "DO_NOT_ARCHIVE_LIVE_NONCE" in artifact._json(unchanged)}, sort_keys=True))

    imported = []
    retained = dict(baseline)
    retained["execute"] = "arbitrary.archived.module"
    def no_import(name, package=None):
        imported.append(name)
        raise AssertionError("retained artifact selected import")
    with patch.object(importlib, "import_module", no_import):
        try:
            artifact.parse_credit_artifact(artifact._json(retained), expected_id="unused")
        except artifact.CreditArtifactError as exc:
            assert exc.code == "credit_artifact_invalid" and imported == []
            print(json.dumps({"case": "unknown_archive_data", "typed_code": exc.code, "imports": imported}, sort_keys=True))
        else:
            raise AssertionError("unknown archive accepted")

    typed = []
    for raw in ("{", "{\"format\":1,\"format\":1}", "{\"format\":NaN}", "{\"format\":1.0}"):
        try:
            artifact.parse_credit_artifact(raw, expected_id="unused")
        except artifact.CreditArtifactError as exc:
            assert exc.code == "credit_artifact_invalid"
            typed.append(exc.code)
        else:
            raise AssertionError("malformed archive accepted")
    print(json.dumps({"case": "strict_parser", "typed_errors": typed}, sort_keys=True))
    assert len(typed) == 4

    required = {"uta.market_cache.MarketDecodeCache.parse", "uta.risk._decimal_exact", "uta.credit_native._verify_financial_source"}
    assert required <= baseline["loaded_credit_engine"].keys()
    assert "uta.scenario_margin._SCENARIOS" in baseline["loaded_credit_constants"]
    assert baseline["activation_permission"] is False
    print(json.dumps({"case": "window", "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.monotonic() - clock,
        "loaded_function_count": len(baseline["loaded_credit_engine"]),
        "loaded_constant_count": len(baseline["loaded_credit_constants"]),
        "required_dependency_functions": sorted(required), "activation_permission": False,
        "sql_used": False, "database_created": False}, sort_keys=True))


if __name__ == "__main__":
    main()
